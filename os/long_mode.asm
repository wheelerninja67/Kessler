[BITS 32]
; ==============================================================================
; KESSLER OS: 32-BIT PROTECTED MODE TO 64-BIT LONG MODE TRANSITION
; Append this to the bootloader to bootstrap the Zig Kernel
; ==============================================================================

; 10. Check if CPU supports CPUID
pushfd
pop eax
mov ecx, eax
xor eax, 1 << 21
push eax
popfd
pushfd
pop eax
push ecx
popfd
cmp eax, ecx
je no_cpuid

; 11. Check if CPU supports Long Mode (64-bit)
mov eax, 0x80000000
cpuid
cmp eax, 0x80000001
jb no_long_mode
mov eax, 0x80000001
cpuid
test edx, 1 << 29
jz no_long_mode

; 12. Set up Paging for 64-bit Mode (Identity Mapping first 2MB)
mov edi, 0x1000    ; Base of Page Map Level 4 (PML4)
mov cr3, edi       ; Point CR3 to PML4
xor eax, eax
mov ecx, 4096
rep stosd          ; Clear page tables
mov edi, cr3

; PML4 [0] -> PDPT
mov dword [edi], 0x2003
add edi, 0x1000

; PDPT [0] -> Page Directory
mov dword [edi], 0x3003
add edi, 0x1000

; Page Directory [0] -> 2MB Page (Identity Mapped)
mov dword [edi], 0x00000083

; 13. Enable PAE (Physical Address Extension)
mov eax, cr4
or eax, 1 << 5
mov cr4, eax

; 14. Enable Long Mode in the EFER MSR
mov ecx, 0xC0000080
rdmsr
or eax, 1 << 8
wrmsr

; 15. Enable Paging (Transition to Compatibility Mode)
mov eax, cr0
or eax, 1 << 31
mov cr0, eax

; 16. Load 64-bit GDT
lgdt [gdt64_descriptor]

; 17. Far jump into 64-bit Code Segment
jmp gdt64_code:init_lm

[BITS 64]
init_lm:
    ; 18. Initialize 64-bit Data Segments
    mov ax, gdt64_data
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax

    ; 19. The Kessler Zig Kernel takes over here
    ; (In a real boot sequence, we jump to the loaded ELF binary entry point)
    cli
    hlt

no_cpuid:
no_long_mode:
    ; Error handling (halt the machine)
    cli
    hlt

; --- 64-Bit GDT ---
gdt64_start:
    dq 0x0                  ; Null Descriptor
gdt64_code equ $ - gdt64_start
    dq 0x00209A0000000000   ; 64-bit Code Descriptor
gdt64_data equ $ - gdt64_start
    dq 0x0000920000000000   ; 64-bit Data Descriptor
gdt64_end:

gdt64_descriptor:
    dw gdt64_end - gdt64_start - 1
    dq gdt64_start
