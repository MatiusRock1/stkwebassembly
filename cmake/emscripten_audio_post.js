// Emscripten's OpenAL feeds Web Audio from a main-thread timer and schedules
// only 100 ms ahead. On phones a frame often takes longer than that, so music
// and engine sounds run dry and stutter; half a second covers slow frames.
AL.QUEUE_LOOKAHEAD = 0.5;
