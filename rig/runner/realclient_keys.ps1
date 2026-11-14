# Plays a real client a little, for realclient.calx: F3, a screenshot, a walk and a jump, another
# screenshot, a chat message, and a last screenshot. With -Shot, only a screenshot with the debug
# screen on. With -Fly, a flight instead: `/calcite flyspeed` typed in the chat, a double jump to
# fly, a climb, then forward for -Seconds; it says "flying" as it starts forward and "stopped" as
# it lets go. Keys go only to the client's own window: before each, that window must be in front,
# or this stops without sending another.
param([int]$ProcessId, [string]$Message, [switch]$Shot, [switch]$Fly, [string]$Speed = "25", [int]$Seconds = 30)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class RealClientWindow {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern short VkKeyScanEx(char c, IntPtr layout);
    [DllImport("user32.dll")] public static extern uint MapVirtualKeyEx(uint code, uint kind, IntPtr layout);
}
"@

$h = (Get-Process -Id $ProcessId).MainWindowHandle
if ($h -eq [IntPtr]::Zero) { Write-Output "the client has no window"; exit 2 }

# Windows lets a process bring a window to the front just after a key, so Alt goes first. It
# doesn't always take the first time, so it's tried a few times.
for ($try = 0; $try -lt 5 -and [RealClientWindow]::GetForegroundWindow() -ne $h; $try++) {
    [RealClientWindow]::ShowWindow($h, 9) | Out-Null
    [RealClientWindow]::keybd_event(0x12, 0x38, 0, [UIntPtr]::Zero)
    [RealClientWindow]::keybd_event(0x12, 0x38, 2, [UIntPtr]::Zero)
    [RealClientWindow]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 300
}

function InFront {
    if ([RealClientWindow]::GetForegroundWindow() -ne $h) { Write-Output "the client's window isn't in front$(Front), so no more keys"; exit 3 }
}

# Whose window is in front, by its process's name alone.
function Front {
    $owner = [uint32]0
    [RealClientWindow]::GetWindowThreadProcessId([RealClientWindow]::GetForegroundWindow(), [ref]$owner) | Out-Null
    $p = Get-Process -Id $owner -ErrorAction SilentlyContinue
    if ($p) { return " ($($p.ProcessName)'s is, process $owner; the client's is $ProcessId)" } else { return "" }
}

# GLFW reads a key by its scan code, so each key is sent with both codes.
function Down([byte]$vk, [byte]$scan) { InFront; [RealClientWindow]::keybd_event($vk, $scan, 0, [UIntPtr]::Zero) }
function Up([byte]$vk, [byte]$scan) { [RealClientWindow]::keybd_event($vk, $scan, 2, [UIntPtr]::Zero) }
function Key([byte]$vk, [byte]$scan, [int]$holdMs) {
    Down $vk $scan
    Start-Sleep -Milliseconds $holdMs
    Up $vk $scan
    Start-Sleep -Milliseconds 60
}

# Types `text` as the client's keyboard layout has each character, with Shift, Ctrl and Alt as it
# needs them, so a slash or a digit comes out as itself whatever the layout.
function TypeText([string]$text) {
    $owner = [uint32]0
    $thread = [RealClientWindow]::GetWindowThreadProcessId($h, [ref]$owner)
    $layout = [RealClientWindow]::GetKeyboardLayout($thread)
    $mods = @(@(1, 0x10, 0x2A), @(2, 0x11, 0x1D), @(4, 0x12, 0x38))
    foreach ($c in $text.ToCharArray()) {
        $code = [RealClientWindow]::VkKeyScanEx($c, $layout)
        if ($code -eq -1) { Write-Output "the client's keyboard layout has no key for '$c'"; exit 4 }
        $vk = [byte]($code -band 0xFF)
        $state = ($code -shr 8) -band 7
        $scan = [byte][RealClientWindow]::MapVirtualKeyEx($vk, 0, $layout)
        foreach ($m in $mods) { if ($state -band $m[0]) { Down $m[1] $m[2] } }
        Key $vk $scan 30
        foreach ($m in $mods) { if ($state -band $m[0]) { Up $m[1] $m[2] } }
    }
}

$scans = @{ 'a'=0x1E; 'b'=0x30; 'c'=0x2E; 'd'=0x20; 'e'=0x12; 'f'=0x21; 'g'=0x22; 'h'=0x23; 'i'=0x17; 'j'=0x24; 'k'=0x25; 'l'=0x26; 'm'=0x32; 'n'=0x31; 'o'=0x18; 'p'=0x19; 'q'=0x10; 'r'=0x13; 's'=0x1F; 't'=0x14; 'u'=0x16; 'v'=0x2F; 'w'=0x11; 'x'=0x2D; 'y'=0x15; 'z'=0x2C; ' '=0x39 }

if ($Shot) {
    Start-Sleep -Milliseconds 300
    Key 0x72 0x3D 80      # F3: the debug screen, which names the dimension
    Start-Sleep -Milliseconds 800
    Key 0x71 0x3C 80      # F2: a screenshot
    Key 0x72 0x3D 80      # F3 off
    Write-Output "sent"
    exit 0
}

if ($Fly) {
    Start-Sleep -Milliseconds 1000
    Key 0x54 0x14 80          # T: chat
    Start-Sleep -Milliseconds 600
    TypeText "/calcite flyspeed $Speed"
    Start-Sleep -Milliseconds 200
    Key 0x0D 0x1C 80          # Enter: run it
    Start-Sleep -Milliseconds 1000
    Key 0x20 0x39 80          # Space twice, quickly: fly
    Start-Sleep -Milliseconds 90
    Key 0x20 0x39 80
    Start-Sleep -Milliseconds 300
    Key 0x20 0x39 700         # Space, held: climb clear of the hills
    Key 0x72 0x3D 80          # F3: the debug screen, with the player's coordinates
    Key 0x71 0x3C 80          # F2: a screenshot before the flight
    Down 0x57 0x11            # W, held: forward
    Write-Output "flying"
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        if ([RealClientWindow]::GetForegroundWindow() -ne $h) {
            Up 0x57 0x11
            Write-Output "the client's window isn't in front$(Front), so no more keys"
            exit 3
        }
        Start-Sleep -Milliseconds 200
    }
    Key 0x71 0x3C 80          # F2: a screenshot as it ends, of how far the chunks reach
    Up 0x57 0x11
    Write-Output "stopped"
    exit 0
}

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
