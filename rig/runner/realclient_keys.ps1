# Plays a real client a little, for realclient.py: F3, a screenshot, a walk and a jump, another
# screenshot, a chat message, and a last screenshot. Keys go only to the client's own window:
# before each, that window must be in front, or this stops without sending another.
param([int]$ProcessId, [string]$Message)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class RealClientWindow {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@

$h = (Get-Process -Id $ProcessId).MainWindowHandle
if ($h -eq [IntPtr]::Zero) { Write-Output "the client has no window"; exit 2 }

# Windows lets a process bring a window to the front just after a key, so Alt goes first.
[RealClientWindow]::ShowWindow($h, 9) | Out-Null
[RealClientWindow]::keybd_event(0x12, 0x38, 0, [UIntPtr]::Zero)
[RealClientWindow]::keybd_event(0x12, 0x38, 2, [UIntPtr]::Zero)
[RealClientWindow]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 300

# GLFW reads a key by its scan code, so each key is sent with both codes.
function Key([byte]$vk, [byte]$scan, [int]$holdMs) {
    if ([RealClientWindow]::GetForegroundWindow() -ne $h) { Write-Output "the client's window isn't in front, so no more keys"; exit 3 }
    [RealClientWindow]::keybd_event($vk, $scan, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds $holdMs
    [RealClientWindow]::keybd_event($vk, $scan, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
}

$scans = @{ 'a'=0x1E; 'b'=0x30; 'c'=0x2E; 'd'=0x20; 'e'=0x12; 'f'=0x21; 'g'=0x22; 'h'=0x23; 'i'=0x17; 'j'=0x24; 'k'=0x25; 'l'=0x26; 'm'=0x32; 'n'=0x31; 'o'=0x18; 'p'=0x19; 'q'=0x10; 'r'=0x13; 's'=0x1F; 't'=0x14; 'u'=0x16; 'v'=0x2F; 'w'=0x11; 'x'=0x2D; 'y'=0x15; 'z'=0x2C; ' '=0x39 }

Start-Sleep -Milliseconds 1500
Key 0x72 0x3D 80          # F3: the debug screen, with the player's coordinates
Start-Sleep -Milliseconds 500
Key 0x71 0x3C 80          # F2: a screenshot before the walk
Start-Sleep -Milliseconds 500
Key 0x57 0x11 2500        # W, held: about 11 blocks forward
Key 0x20 0x39 80          # Space: a jump
Start-Sleep -Milliseconds 800
Key 0x71 0x3C 80          # F2: after it
Key 0x72 0x3D 80          # F3 off
Key 0x54 0x14 80          # T: chat
Start-Sleep -Milliseconds 600
foreach ($c in $Message.ToLower().ToCharArray()) {
    $vk = if ($c -eq ' ') { 0x20 } else { [byte][char]::ToUpper($c) }
    Key $vk $scans[[string]$c] 30
}
Start-Sleep -Milliseconds 300
Key 0x0D 0x1C 80          # Enter: send it
Start-Sleep -Milliseconds 1500
Key 0x71 0x3C 80          # F2: the message in the chat
Write-Output "sent"
