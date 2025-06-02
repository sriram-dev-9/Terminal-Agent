import subprocess
import uuid
import time

class Process:
    def __init__(self):
        self.process = subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self._clear_initial_output()
        self.pending_output = ""

    def _clear_initial_output(self):
        """Clear startup banner from PowerShell."""
        time.sleep(1.0)  
        self._drain_output()

    def _drain_output(self):
        """Drain any pending output from the buffer."""
        output = ""
        try:
            import msvcrt
            while msvcrt.kbhit():
                line = self.process.stdout.readline()
                if not line:
                    break
                output += line
        except Exception:
            try:
                while self.process.poll() is None:
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    output += line
            except:
                pass
        return output

    def send_command(self, cmd: str) -> str:
        """Send command to PowerShell and retrieve complete output."""
        pending = self._drain_output()
        if pending:
            self.pending_output += pending

        unique_id = str(uuid.uuid4())
        start_marker = f"<<<<START_MARKER_{unique_id}>>>>"
        end_marker = f"<<<<END_MARKER_{unique_id}>>>>"
        wrapped_cmd = f"""
Write-Output "{start_marker}"
{cmd}
Write-Output "{end_marker}"
"""
        self.process.stdin.write(wrapped_cmd + '\n')
        self.process.stdin.flush()
        
        output = self._read_between_markers(start_marker, end_marker)
        return output

    def _read_between_markers(self, start_marker, end_marker, max_attempts=50):
        """Read all output between start and end markers."""
        full_output = self.pending_output
        self.pending_output = "" 
        
        found_start = False
        found_end = False
        start_pos = -1
        end_pos = -1
        
        attempts = 0
        while attempts < max_attempts and not found_end:
            attempts += 1
            line = self.process.stdout.readline()
            if not line:
                time.sleep(0.2) 
                continue
                
            full_output += line
            
            if not found_start and start_marker in full_output:
                found_start = True
                start_pos = full_output.find(start_marker) + len(start_marker)
            
            if found_start and end_marker in full_output:
                found_end = True
                end_pos = full_output.find(end_marker)

        if found_start and found_end:
            result = full_output[start_pos:end_pos].strip()
            self.pending_output = full_output[end_pos + len(end_marker):]
            return result
        else:
            return full_output + "\n[Warning: Command output may be incomplete]"