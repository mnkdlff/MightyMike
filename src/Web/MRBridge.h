// MiReina bridge — the page writes this block into wasm memory; the engine reads it in UpdateInput.
// Layout is shared with lib/pete.ts (MR offsets) and mireina/tools/dev.html. 32 bytes, little-endian.
#pragma once

#include <stdint.h>
#include <stdbool.h>

typedef struct MRInput
{
	int16_t  lx, ly, rx, ry;	// virtual sticks, -32767..32767, y grows downwards (SDL convention)
	uint8_t  held[8];			// MR_HELD_*: 1 while pressed
	uint8_t  pulse[8];			// MR_PULSE_*: counters, one engine press per increment
	uint8_t  textChar;			// ASCII typed on the page, consumed by MR_TakeTextChar
	int8_t   loadSlot;			// -1 let the game ask, 0 new game (dialog skipped), 1..4 restore that slot
	uint8_t  music, sfx, audioDirty;
	uint8_t  exitRequested;
	uint8_t  active;			// 1 while a finger drives the sticks: the virtual device beats the gamepad
	uint8_t  pad;
} MRInput;

enum { MR_HELD_ATTACK, MR_HELD_PREVWEAPON, MR_HELD_NEXTWEAPON, MR_HELD_RADAR, MR_HELD_UP, MR_HELD_DOWN, MR_HELD_LEFT, MR_HELD_RIGHT };
enum { MR_PULSE_CONFIRM, MR_PULSE_BACK, MR_PULSE_PAUSE, MR_PULSE_PREVWEAPON, MR_PULSE_NEXTWEAPON, MR_PULSE_RADAR, MR_PULSE_ENTER, MR_PULSE_BACKSPACE };

extern MRInput gMR;

void    MR_Boot(void);					// publish the block to the page, emit "boot"
void    MR_Tick(void);					// once per UpdateInput: pulses, audio, exit
bool    MR_NeedDown(int needID);		// virtual contribution to a kNeed_* (held / stick / pulse)
bool    MR_Pulsed(int pulseID);			// true on the frame a MR_PULSE_* counter advanced
bool    MR_VirtualActive(void);
int32_t MR_LeftMagnitude_Fix32(void);	// same scale as GetLeftStickMagnitude_Fix32
short   MR_RightAim(void);				// AIM_* or AIM_NONE
char    MR_TakeTextChar(void);			// the typed char, then 0

#if MR_WEB
void MR_Emit(const char* kind, int a, int b);
void MR_EmitStr(const char* kind, const char* s);
#define MR_EMIT(kind, a, b)		MR_Emit((kind), (int)(a), (int)(b))
#define MR_EMIT_STR(kind, s)	MR_EmitStr((kind), (s))
#else
#define MR_EMIT(kind, a, b)		((void)0)
#define MR_EMIT_STR(kind, s)	((void)0)
#endif
