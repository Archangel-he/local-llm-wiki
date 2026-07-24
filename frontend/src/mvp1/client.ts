import type { Mvp1Client } from "./contracts";
import { MockMvp1Client } from "./mockClient";

let client: Mvp1Client | null = null;

export function getMvp1Client(): Mvp1Client {
  if (!client) {
    client = new MockMvp1Client();
  }
  return client;
}
