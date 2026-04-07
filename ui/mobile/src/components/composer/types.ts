/** 5-state machine for the Composer input bar. */
export type ComposerState =
  | 'idle_empty'   // text is empty — send button disabled (gray)
  | 'idle_ready'   // text is non-empty — send button enabled (blue)
  | 'sending'      // sendTurn in-flight — button disabled + spinner
  | 'streaming'    // backend is responding — stop button shown
  | 'cancelling';  // cancel POST sent, awaiting turn_complete — button disabled + spinner
