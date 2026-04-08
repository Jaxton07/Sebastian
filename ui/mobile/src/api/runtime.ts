interface ApiRuntimeState {
  serverUrl: string;
  jwtToken: string | null;
}

let runtimeState: ApiRuntimeState = {
  serverUrl: '',
  jwtToken: null,
};

let unauthorizedHandler: (() => Promise<void> | void) | null = null;

export function getApiRuntimeState(): ApiRuntimeState {
  return runtimeState;
}

export function setApiRuntimeState(nextState: ApiRuntimeState): void {
  runtimeState = nextState;
}

export function setUnauthorizedHandler(handler: (() => Promise<void> | void) | null): void {
  unauthorizedHandler = handler;
}

export async function handleUnauthorizedResponse(): Promise<void> {
  await unauthorizedHandler?.();
}

export function resetApiRuntimeForTests(): void {
  runtimeState = { serverUrl: '', jwtToken: null };
  unauthorizedHandler = null;
}
