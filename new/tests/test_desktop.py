import threading
import unittest
from unittest.mock import MagicMock, patch

from desktop import LocalServer


class DesktopLifecycleTests(unittest.TestCase):
    def test_invalid_port_does_not_start(self):
        for port in [0, 80, 65536]:
            with self.assertRaises(ValueError):
                LocalServer().start(port)

    def test_port_conflict_cleans_up_workers(self):
        controller = LocalServer()
        with patch('desktop.create_app'), patch('desktop.socket.socket'), patch('waitress.create_server', side_effect=OSError('port busy')), patch('waitress.task.ThreadedTaskDispatcher') as dispatcher:
            with self.assertRaises(OSError):
                controller.start(8000)
            dispatcher.return_value.shutdown.assert_called_once()
            self.assertIsNone(controller.server)

    def test_stop_waits_for_server_and_allows_restart(self):
        controller = LocalServer()
        for _ in range(2):
            finished = threading.Event()
            server = MagicMock()
            server.run.side_effect = lambda: finished.wait(5)
            server.close.side_effect = finished.set
            connection = MagicMock()
            with patch('desktop.create_app'), patch('desktop.socket.socket'), patch('waitress.create_server', return_value=server), patch('waitress.task.ThreadedTaskDispatcher'):
                controller.start(8000)
                thread = controller.thread
                controller.connections[1] = connection
                self.assertTrue(thread.is_alive())
                self.assertTrue(controller.password)
                with self.assertRaises(RuntimeError):
                    controller.start(8000)
                controller.stop()
                self.assertFalse(thread.is_alive())
                self.assertIsNone(controller.server)
                self.assertEqual(controller.password, '')
                server.task_dispatcher.shutdown.assert_called_once()
                connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
