import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from Smart_Bridge_POC.process import StdioProcess
from Smart_Bridge_POC.framing import encode_framed_json, read_framed_json

@pytest.mark.asyncio
async def test_stdio_process_start():
    mock_proc = AsyncMock()
    mock_proc.stdout = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.readline.return_value = b'' # Simulate EOF for stderr

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc) as mock_create_subprocess_shell:
        process = StdioProcess(cmd='echo hello')
        await process.start()

        mock_create_subprocess_shell.assert_called_once_with(
            'echo hello',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=None,
            env=os.environ.copy(),
        )
        assert process.proc == mock_proc
        assert process.reader == mock_proc.stdout
        assert process.writer == mock_proc.stdin
        assert process.stderr_task is not None
        process.stderr_task.cancel() # Clean up the task

@pytest.mark.asyncio
async def test_stdio_process_write_json():
    mock_proc = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdout = AsyncMock()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.readline.return_value = b''

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        process = StdioProcess(cmd='test')
        await process.start()

        test_obj = {"method": "test", "params": []}
        await process.write_json(test_obj)

        expected_payload = encode_framed_json(test_obj)
        process.writer.write.assert_called_once_with(expected_payload)
        process.writer.drain.assert_awaited_once()
        process.stderr_task.cancel()

@pytest.mark.asyncio
async def test_stdio_process_read_json():
    mock_proc = AsyncMock()
    mock_proc.stdout = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.readline.return_value = b''

    test_obj = {"result": "success"}
    framed_data = encode_framed_json(test_obj)

    # Mock the stdout to return framed data chunk by chunk
    mock_proc.stdout.read.side_effect = [framed_data[i:i+1] for i in range(len(framed_data))] + [b'']

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        process = StdioProcess(cmd='test')
        await process.start()

        read_data = await process.read_json()
        assert read_data == test_obj
        process.stderr_task.cancel()

@pytest.mark.asyncio
async def test_stdio_process_stderr_logging():
    mock_proc = AsyncMock()
    mock_proc.stdout = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stderr = AsyncMock()

    # Simulate stderr output line by line
    mock_proc.stderr.readline.side_effect = [b'Error line 1\n', b'Warning line 2\n', b'']

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        with patch('Smart_Bridge_POC.process.logger.info') as mock_logger_info:
            process = StdioProcess(cmd='test')
            await process.start()

            # Allow some time for the stderr pump to process lines
            await asyncio.sleep(0.1)

            mock_logger_info.assert_any_call('[server stderr] %s', 'Error line 1')
            mock_logger_info.assert_any_call('[server stderr] %s', 'Warning line 2')
            process.stderr_task.cancel()
