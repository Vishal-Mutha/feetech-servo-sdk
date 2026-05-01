"""Tests for the servo ID scan example."""

import argparse

import pytest

import scservo_sdk as scs
from examples.scan_motor_ids import scan_ids, validate_args


class FakePacketHandler:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def ping(self, servo_id):
        self.calls.append(servo_id)
        return self.responses.get(servo_id, (0, scs.COMM_RX_TIMEOUT, 0))


def make_args(**overrides):
    values = {
        "start_id": 0,
        "end_id": 253,
        "retries": 1,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_scan_ids_returns_responding_ids():
    packet_handler = FakePacketHandler(
        {
            1: (1234, scs.COMM_SUCCESS, 0),
            3: (5678, scs.COMM_SUCCESS, 0),
        }
    )

    assert scan_ids(packet_handler, range(1, 5), retries=1) == [
        (1, 1234, 0),
        (3, 5678, 0),
    ]


def test_scan_ids_retries_until_success():
    class RetryPacketHandler:
        def __init__(self):
            self.calls = 0

        def ping(self, servo_id):
            self.calls += 1
            if self.calls == 1:
                return 0, scs.COMM_RX_TIMEOUT, 0
            return 4321, scs.COMM_SUCCESS, 0

    packet_handler = RetryPacketHandler()

    assert scan_ids(packet_handler, [7], retries=2) == [(7, 4321, 0)]
    assert packet_handler.calls == 2


@pytest.mark.parametrize(
    "args",
    [
        make_args(start_id=-1),
        make_args(end_id=254),
        make_args(start_id=10, end_id=9),
        make_args(retries=0),
    ],
)
def test_validate_args_rejects_invalid_values(args):
    with pytest.raises(SystemExit):
        validate_args(args)
