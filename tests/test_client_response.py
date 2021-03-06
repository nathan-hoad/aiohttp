# -*- coding: utf-8 -*-
"""Tests for aiohttp/client.py"""

import asyncio
import gc
import unittest
import unittest.mock

import aiohttp
from aiohttp.client_reqrep import ClientResponse


class TestClientResponse(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

        self.connection = unittest.mock.Mock()
        self.stream = aiohttp.StreamParser(loop=self.loop)
        self.response = ClientResponse('get', 'http://def-cl-resp.org')
        self.response._post_init(self.loop)
        self.response._setup_connection(self.connection)

    def tearDown(self):
        self.response.close()
        self.loop.close()
        gc.collect()

    def test_del(self):
        response = ClientResponse('get', 'http://del-cl-resp.org')
        response._post_init(self.loop)

        connection = unittest.mock.Mock()
        response._setup_connection(connection)
        self.loop.set_exception_handler(lambda loop, ctx: None)

        with self.assertWarns(ResourceWarning):
            del response
            gc.collect()

        connection.close.assert_called_with()

    def test_close(self):
        self.response._connection = self.connection
        self.response.close()
        self.assertIsNone(self.response.connection)
        self.response.close()
        self.response.close()

    def test_wait_for_100_1(self):
        response = ClientResponse(
            'get', 'http://python.org', continue100=object())
        response._post_init(self.loop)
        self.assertTrue(response.waiting_for_continue())
        response.close()

    def test_wait_for_100_2(self):
        response = ClientResponse(
            'get', 'http://python.org')
        response._post_init(self.loop)
        self.assertFalse(response.waiting_for_continue())
        response.close()

    def test_repr(self):
        self.response.status = 200
        self.response.reason = 'Ok'
        self.assertIn(
            '<ClientResponse(http://def-cl-resp.org) [200 Ok]>',
            repr(self.response))

    def test_read_and_release_connection(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result(b'payload')
            return fut
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        res = self.loop.run_until_complete(self.response.read())
        self.assertEqual(res, b'payload')
        self.assertIsNone(self.response._connection)

    def test_read_and_release_connection_with_error(self):
        content = self.response.content = unittest.mock.Mock()
        content.read.return_value = asyncio.Future(loop=self.loop)
        content.read.return_value.set_exception(ValueError)

        self.assertRaises(
            ValueError,
            self.loop.run_until_complete, self.response.read())
        self.assertTrue(self.response._closed)

    def test_release(self):
        fut = asyncio.Future(loop=self.loop)
        fut.set_result(b'')
        content = self.response.content = unittest.mock.Mock()
        content.readany.return_value = fut

        self.loop.run_until_complete(self.response.release())
        self.assertIsNone(self.response._connection)

    def test_read_and_close(self):
        self.response.read = unittest.mock.Mock()
        self.response.read.return_value = asyncio.Future(loop=self.loop)
        self.response.read.return_value.set_result(b'data')

        with self.assertWarns(DeprecationWarning):
            res = self.loop.run_until_complete(self.response.read_and_close())
        self.assertEqual(res, b'data')
        self.assertTrue(self.response.read.called)

    def test_read_decode_deprecated(self):
        self.response._content = b'data'
        self.response.json = unittest.mock.Mock()
        self.response.json.return_value = asyncio.Future(loop=self.loop)
        self.response.json.return_value.set_result('json')

        with self.assertWarns(DeprecationWarning):
            res = self.loop.run_until_complete(self.response.read(decode=True))
        self.assertEqual(res, 'json')
        self.assertTrue(self.response.json.called)

    def test_text(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {
            'CONTENT-TYPE': 'application/json;charset=cp1251'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        res = self.loop.run_until_complete(self.response.text())
        self.assertEqual(res, '{"тест": "пройден"}')
        self.assertIsNone(self.response._connection)

    def test_text_custom_encoding(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {
            'CONTENT-TYPE': 'application/json'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect
        self.response._get_encoding = unittest.mock.Mock()

        res = self.loop.run_until_complete(
            self.response.text(encoding='cp1251'))
        self.assertEqual(res, '{"тест": "пройден"}')
        self.assertIsNone(self.response._connection)
        self.assertFalse(self.response._get_encoding.called)

    def test_text_detect_encoding(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {'CONTENT-TYPE': 'application/json'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        self.loop.run_until_complete(self.response.read())
        res = self.loop.run_until_complete(self.response.text())
        self.assertEqual(res, '{"тест": "пройден"}')
        self.assertIsNone(self.response._connection)

    def test_text_after_read(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {
            'CONTENT-TYPE': 'application/json;charset=cp1251'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        res = self.loop.run_until_complete(self.response.text())
        self.assertEqual(res, '{"тест": "пройден"}')
        self.assertIsNone(self.response._connection)

    def test_json(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {
            'CONTENT-TYPE': 'application/json;charset=cp1251'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        res = self.loop.run_until_complete(self.response.json())
        self.assertEqual(res, {'тест': 'пройден'})
        self.assertIsNone(self.response._connection)

    def test_json_custom_loader(self):
        self.response.headers = {
            'CONTENT-TYPE': 'application/json;charset=cp1251'}
        self.response._content = b'data'

        def custom(content):
            return content + '-custom'

        res = self.loop.run_until_complete(self.response.json(loads=custom))
        self.assertEqual(res, 'data-custom')

    @unittest.mock.patch('aiohttp.client_reqrep.client_logger')
    def test_json_no_content(self, m_log):
        self.response.headers = {
            'CONTENT-TYPE': 'data/octet-stream'}
        self.response._content = b''

        res = self.loop.run_until_complete(self.response.json())
        self.assertIsNone(res)
        m_log.warning.assert_called_with(
            'Attempt to decode JSON with unexpected mimetype: %s',
            'data/octet-stream')

    def test_json_override_encoding(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {
            'CONTENT-TYPE': 'application/json;charset=utf8'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect
        self.response._get_encoding = unittest.mock.Mock()

        res = self.loop.run_until_complete(
            self.response.json(encoding='cp1251'))
        self.assertEqual(res, {'тест': 'пройден'})
        self.assertIsNone(self.response._connection)
        self.assertFalse(self.response._get_encoding.called)

    def test_json_detect_encoding(self):
        def side_effect(*args, **kwargs):
            fut = asyncio.Future(loop=self.loop)
            fut.set_result('{"тест": "пройден"}'.encode('cp1251'))
            return fut
        self.response.headers = {'CONTENT-TYPE': 'application/json'}
        content = self.response.content = unittest.mock.Mock()
        content.read.side_effect = side_effect

        res = self.loop.run_until_complete(self.response.json())
        self.assertEqual(res, {'тест': 'пройден'})
        self.assertIsNone(self.response._connection)

    def test_override_flow_control(self):
        class MyResponse(ClientResponse):
            flow_control_class = aiohttp.FlowControlDataQueue
        response = MyResponse('get', 'http://my-cl-resp.org')
        response._post_init(self.loop)
        response._setup_connection(self.connection)
        self.assertIsInstance(response.content, aiohttp.FlowControlDataQueue)
        response.close()

    @unittest.mock.patch('aiohttp.client_reqrep.chardet')
    def test_get_encoding_unknown(self, m_chardet):
        m_chardet.detect.return_value = {'encoding': None}

        self.response.headers = {'CONTENT-TYPE': 'application/json'}
        self.assertEqual(self.response._get_encoding(), 'utf-8')

    def test_close_deprecated(self):
        self.response._connection = self.connection
        with self.assertWarns(DeprecationWarning):
            self.response.close(force=False)
        self.assertIsNone(self.response._connection)
