; ==============================================================================
; KESSLER OS BOOTLOADER (RING-0)
; Architecture: x86_64
; Purpose: Initialize hardware, secure memory, load the Kessler Zig Engine
; ==============================================================================

[BITS 16]           ; Start in 16-bit Real Mode
[ORG 0x7C00]        ; BIOS loads the bootloader here

boot_start:
    ; 1. Disable Interrupts (We control everything)
    cli

    ; 2. Set up Segment Registers
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00

    ; 3. Print "KESSLER OS INTIALIZING..." to VGA text buffer
    mov si, boot_msg
print_string:
    lodsb
    or al, al
    jz enable_a20
    mov ah, 0x0E    ; BIOS teletype output
    int 0x10
    jmp print_string

enable_a20:
    ; 4. Enable A20 Line (Access memory > 1MB)
    in al, 0x92
    or al, 2
    out 0x92, al

    ; 5. Load GDT (Global Descriptor Table) to transition to 32-bit Protected Mode
    lgdt [gdt_descriptor]

    ; 6. Enable Protected Mode (Set PE bit in CR0)
    mov eax, cr0
    or eax, 1
    mov cr0, eax

    ; 7. Jump to 32-bit code segment (Far Jump)
    jmp 0x08:init_pm

[BITS 32]
init_pm:
    ; 8. Setup 32-bit Data Segments
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000 ; Move stack safely away

    ; 9. HALT until Kernel is loaded
    ; (In full OS, we would now load the Kessler Zig Kernel via disk interrupts)
    cli
    hlt

; --- DATA ---
boot_msg db 'KESSLER OS [RING-0] INITIALIZING SECURE HARDWARE...', 13, 10, 0

; --- GDT Setup ---
gdt_start:
    dq 0x0 ; Null Descriptor
gdt_code:
    dw 0xFFFF, 0x0000, 0x9A00, 0x00CF ; 32-bit Code Segment
gdt_data:
    dw 0xFFFF, 0x0000, 0x9200, 0x00CF ; 32-bit Data Segment
gdt_end:

gdt_descriptor:
    dw gdt_end - gdt_start - 1
    dd gdt_start

; Boot Sector Signature (Must be exactly 512 bytes)
times 510-($-$$) db 0
dw 0xAA55
