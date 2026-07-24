import type { Mvp1Client } from "./contracts";
import { HttpMvp1Client } from "./httpClient";
import { MockMvp1Client } from "./mockClient";

let client: Mvp1Client | null = null;

export function getMvp1Client(): Mvp1Client {
  if (!client) {
    const useMock =
      import.meta.env.VITE_USE_MOCK_MVP1 === "true" ||
      import.meta.env.MODE === "test";
    client = useMock ? new MockMvp1Client() : new HttpMvp1Client();
  }
  return client;
}
