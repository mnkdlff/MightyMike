// MiReina bridge: see MRBridge.h. Compiles on every platform; the EM_JS parts only exist on the web.
#include "myglobals.h"
#include "misc.h"
#include "sound2.h"
#include "main.h"
#include "input.h"
#include "externs.h"
#include "MRBridge.h"

#include <SDL3/SDL.h>
#include <math.h>
#include <string.h>

#if MR_WEB
#include <emscripten/emscripten.h>

EM_JS(void, MR_JS_SetInputBuffer, (void* ptr, int size), {
	if (typeof Module.mrOnInputBuffer === "function") Module.mrOnInputBuffer(ptr, size);
});
EM_JS(void, MR_JS_Event, (const char* kind, int a, int b), {
	window.dispatchEvent(new CustomEvent("powerpete", { detail: { kind: UTF8ToString(kind), a: a, b: b } }));
});
EM_JS(void, MR_JS_Str, (const char* kind, const char* s), {
	window.dispatchEvent(new CustomEvent("powerpete", { detail: { kind: UTF8ToString(kind), s: UTF8ToString(s) } }));
});

void MR_Emit(const char* kind, int a, int b)		{ MR_JS_Event(kind, a, b); }
void MR_EmitStr(const char* kind, const char* s)	{ MR_JS_Str(kind, s); }
#endif

MRInput gMR;
_Static_assert(sizeof(MRInput) == 32, "MRInput layout is shared with the page (lib/pete.ts)");

static uint8_t  gLastPulse[8];
static uint8_t  gPulsed[8];
static uint32_t gTick;

#define MR_DEADZONE		(33 * 32767 / 100)
#define MR_DEADZONE_UI	(66 * 32767 / 100)
#define MR_FIRE_REPEAT	6		// sim frames between two "new presses" while the aim stick is held

void MR_Boot(void)
{
	memset(&gMR, 0, sizeof gMR);
	memset(gLastPulse, 0, sizeof gLastPulse);
	gMR.loadSlot = -1;
	gMR.music = 1;
	gMR.sfx = 1;
#if MR_WEB
	MR_JS_SetInputBuffer(&gMR, (int) sizeof gMR);
	MR_EMIT("boot", 0, 0);
#endif
}

void MR_Tick(void)
{
	gTick++;

	for (int i = 0; i < 8; i++)
	{
		gPulsed[i] = (gMR.pulse[i] != gLastPulse[i]);
		gLastPulse[i] = gMR.pulse[i];
	}

	if (gMR.audioDirty)
	{
		gMR.audioDirty = 0;
		gGamePrefs.music = gMR.music ? true : false;
		gGamePrefs.soundEffects = gMR.sfx ? true : false;
		OnToggleMusic();
		SavePrefs();
	}

	if (gMR.exitRequested)
	{
		gMR.exitRequested = 0;
		CleanQuit();				// emits "exit" itself
	}
}

bool MR_Pulsed(int pulseID)			{ return gPulsed[pulseID] != 0; }
bool MR_VirtualActive(void)			{ return gMR.active != 0; }

static bool DirDown(int needID, int dz)
{
	switch (needID)
	{
		case kNeed_Up:		case kNeed_UIUp:	return gMR.ly < -dz;
		case kNeed_Down:	case kNeed_UIDown:	return gMR.ly >  dz;
		case kNeed_Left:	case kNeed_UILeft:	return gMR.lx < -dz;
		case kNeed_Right:	case kNeed_UIRight:	return gMR.lx >  dz;
		default:								return false;
	}
}

static bool AimHeld(void)
{
	int dx = gMR.rx, dy = gMR.ry;
	return dx * dx + dy * dy > MR_DEADZONE * MR_DEADZONE;
}

bool MR_NeedDown(int needID)
{
	switch (needID)
	{
		case kNeed_Up:		return gMR.held[MR_HELD_UP]    || DirDown(needID, MR_DEADZONE);
		case kNeed_Down:	return gMR.held[MR_HELD_DOWN]  || DirDown(needID, MR_DEADZONE);
		case kNeed_Left:	return gMR.held[MR_HELD_LEFT]  || DirDown(needID, MR_DEADZONE);
		case kNeed_Right:	return gMR.held[MR_HELD_RIGHT] || DirDown(needID, MR_DEADZONE);

		case kNeed_UIUp:	case kNeed_UIDown:
		case kNeed_UILeft:	case kNeed_UIRight:
			return DirDown(needID, MR_DEADZONE_UI);

		case kNeed_Attack:
			if (gMR.held[MR_HELD_ATTACK]) return true;
			if (AimHeld()) return (gTick % MR_FIRE_REPEAT) != 0;		// released one frame in six: re-triggers "new press" weapons
			return false;

		case kNeed_PrevWeapon:	return gMR.held[MR_HELD_PREVWEAPON] || gPulsed[MR_PULSE_PREVWEAPON];
		case kNeed_NextWeapon:	return gMR.held[MR_HELD_NEXTWEAPON] || gPulsed[MR_PULSE_NEXTWEAPON];
		case kNeed_Radar:		return gMR.held[MR_HELD_RADAR]      || gPulsed[MR_PULSE_RADAR];
		case kNeed_UIConfirm:	return gPulsed[MR_PULSE_CONFIRM];
		case kNeed_UIBack:		return gPulsed[MR_PULSE_BACK];
		case kNeed_UIPause:		return gPulsed[MR_PULSE_PAUSE];
		default:				return false;
	}
}

int32_t MR_LeftMagnitude_Fix32(void)
{
	int dx = gMR.lx, dy = gMR.ly;
	int m2 = dx * dx + dy * dy;
	if (m2 < MR_DEADZONE * MR_DEADZONE)
		return 0;
	float m = sqrtf((float) m2) / 32767.0f;
	if (m > 1.0f) m = 1.0f;
	return (int32_t)(0x10000 * m);
}

short MR_RightAim(void)
{
	int dx = gMR.rx, dy = gMR.ry;
	bool right = dx >  MR_DEADZONE;
	bool left  = dx < -MR_DEADZONE;
	bool down  = dy >  MR_DEADZONE;
	bool up    = dy < -MR_DEADZONE;

	if (down)	return right ? AIM_DOWN_RIGHT : left ? AIM_DOWN_LEFT : AIM_DOWN;
	if (up)		return right ? AIM_UP_RIGHT   : left ? AIM_UP_LEFT   : AIM_UP;
	return right ? AIM_RIGHT : left ? AIM_LEFT : AIM_NONE;
}

char MR_TakeTextChar(void)
{
	char c = (char) gMR.textChar;
	gMR.textChar = 0;
	return c;
}
