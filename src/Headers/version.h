#pragma once

#define GAME_NAME			"MightyMike"
#define GAME_FULL_NAME		"Mighty Mike"
#define GAME_IDENTIFIER		"io.jor.mightymike"
#define GAME_VERSION		"3.0.3"
#define GAME_VERSION_MAJOR	3
#define GAME_VERSION_MINOR	0
#define GAME_VERSION_PATCH	3

// The web edition's window title (SDL mirrors it into document.title).
#if MR_WEB
#define MR_WINDOW_TITLE		"Power Reina"
#else
#define MR_WINDOW_TITLE		GAME_FULL_NAME " " GAME_VERSION
#endif
