"""钉钉与企业微信群机器人的消息解析 / 派发测试。

这些用例不连接真实平台，只验证「从回调帧里取到对的人、对的问题」
以及回复走的是哪个通道。
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from apps.system.core import robot_manager as robot


def test_platform_mapping_is_distinct():
    assert robot.PLATFORM_USER_ORIGIN == {"feishu": 8, "dingtalk": 7, "wecom": 6}
    assert robot.PLATFORM_CHAT_ORIGIN == {"feishu": 3, "dingtalk": 4, "wecom": 5}
    assert robot.SUPPORTED_PLATFORMS == ("feishu", "dingtalk", "wecom")
    for worker_class in robot.WORKER_CLASSES.values():
        assert worker_class.user_origin
        assert worker_class.chat_origin


def _dingtalk_payload(**overrides):
    payload = {
        "msgtype": "text",
        "text": {"content": " 帮我看看本月销量 "},
        "msgId": "msg-1",
        "senderStaffId": "staff-1",
        "senderId": "user-1",
        "conversationId": "cid-1",
        "conversationType": "2",
        "sessionWebhook": "https://example.invalid/hook",
        "robotCode": "ding123",
    }
    payload.update(overrides)
    return payload


def test_dingtalk_dispatches_question_with_sender_ids():
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._executor.submit = Mock()

    worker._on_message(_dingtalk_payload())

    args = worker._executor.submit.call_args.args
    assert args[0] == worker._process
    assert args[1] == "帮我看看本月销量"
    assert args[2] == {"staff-1", "user-1"}
    assert args[3].message_id == "msg-1"
    worker._slots.release()


@pytest.mark.parametrize(
    "overrides",
    [
        {"msgtype": "picture"},
        {"text": {"content": "   "}},
        {"conversationId": None},
        {"senderStaffId": None},
        {"senderId": "$:LWCP_v1:$bot"},
    ],
)
def test_dingtalk_ignores_unsupported_messages(overrides):
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._executor.submit = Mock()

    worker._on_message(_dingtalk_payload(**overrides))

    worker._executor.submit.assert_not_called()


def test_dingtalk_deduplicates_same_message_id():
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._executor.submit = Mock()

    worker._on_message(_dingtalk_payload())
    worker._on_message(_dingtalk_payload())

    assert worker._executor.submit.call_count == 1
    worker._slots.release()


def test_dingtalk_reply_sends_privately_to_requester(monkeypatch):
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._client = Mock()
    worker._client.get_access_token.return_value = "access-token"
    posted = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"processQueryKey": "query-1"}

    def fake_post(url, **kwargs):
        posted["url"] = url
        posted["headers"] = kwargs["headers"]
        posted["payload"] = kwargs["json"]
        return _Resp()

    monkeypatch.setattr(robot.requests, "post", fake_post)
    msg = Mock(sender_staff_id="staff-1", robot_code="ding123")

    assert worker._reply_text(msg, "共 3 行") is True
    assert posted["url"] == "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
    assert posted["headers"] == {"x-acs-dingtalk-access-token": "access-token"}
    assert posted["payload"]["robotCode"] == "ding123"
    assert posted["payload"]["userIds"] == ["staff-1"]
    assert posted["payload"]["msgKey"] == "sampleText"
    assert json.loads(posted["payload"]["msgParam"]) == {"content": "共 3 行"}


def test_dingtalk_does_not_send_without_private_user_id(monkeypatch):
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._client = Mock()
    post = Mock()
    monkeypatch.setattr(robot.requests, "post", post)

    assert not worker._reply_text(Mock(sender_staff_id=None), "private answer")
    post.assert_not_called()


def test_dingtalk_token_error_does_not_escape_private_send(monkeypatch):
    worker = robot.DingTalkRobotWorker("appkey", "secret")
    worker._client = Mock()
    worker._client.get_access_token.side_effect = RuntimeError("token unavailable")
    post = Mock()
    monkeypatch.setattr(robot.requests, "post", post)

    assert not worker._reply_text(Mock(sender_staff_id="staff-1"), "private answer")
    post.assert_not_called()


def _wecom_frame(**body_overrides):
    body = {
        "msgid": "wx-msg-1",
        "chattype": "single",
        "from": {"userid": "zhangsan"},
        "msgtype": "text",
        "text": {"content": "上个月华东的销售额"},
    }
    body.update(body_overrides)
    return {"cmd": "aibot_msg_callback", "body": body}


def test_wecom_dispatches_question_with_userid():
    worker = robot.WeComRobotWorker("bot-id", "bot-secret")
    worker._executor.submit = Mock()

    asyncio.run(worker._on_frame(_wecom_frame()))

    args = worker._executor.submit.call_args.args
    assert args[0] == worker._process
    assert args[1] == "上个月华东的销售额"
    assert args[2] == {"zhangsan"}
    assert args[3]["body"]["msgid"] == "wx-msg-1"
    worker._slots.release()


def test_wecom_delivery_targets_requester_private_chat():
    worker = robot.WeComRobotWorker("bot-id", "bot-secret")
    worker._client = Mock()
    worker._client.send_message = AsyncMock()

    asyncio.run(worker._deliver("zhangsan", "private answer", None))

    worker._client.send_message.assert_awaited_once_with(
        "zhangsan",
        {"msgtype": "markdown", "markdown": {"content": "private answer"}},
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"msgtype": "image"},
        {"from": {}},
        {"text": {"content": "  "}},
    ],
)
def test_wecom_ignores_unsupported_frames(overrides):
    worker = robot.WeComRobotWorker("bot-id", "bot-secret")
    worker._executor.submit = Mock()

    asyncio.run(worker._on_frame(_wecom_frame(**overrides)))

    worker._executor.submit.assert_not_called()


def test_wecom_deduplicates_same_msgid():
    worker = robot.WeComRobotWorker("bot-id", "bot-secret")
    worker._executor.submit = Mock()

    asyncio.run(worker._on_frame(_wecom_frame()))
    asyncio.run(worker._on_frame(_wecom_frame()))

    assert worker._executor.submit.call_count == 1
    worker._slots.release()
