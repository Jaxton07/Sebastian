import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getApiRuntimeState,
  handleUnauthorizedResponse,
  resetApiRuntimeForTests,
  setApiRuntimeState,
  setUnauthorizedHandler,
} from './runtime';

describe('api runtime', () => {
  beforeEach(() => {
    resetApiRuntimeForTests();
  });

  it('stores the latest server url and jwt token for api client access', () => {
    setApiRuntimeState({ serverUrl: 'http://10.0.2.2:8000', jwtToken: 'token-1' });

    expect(getApiRuntimeState()).toEqual({
      serverUrl: 'http://10.0.2.2:8000',
      jwtToken: 'token-1',
    });
  });

  it('invokes the registered unauthorized handler when a 401 is received', async () => {
    const handler = vi.fn(async () => {});
    setUnauthorizedHandler(handler);

    await handleUnauthorizedResponse();

    expect(handler).toHaveBeenCalledTimes(1);
  });
});
