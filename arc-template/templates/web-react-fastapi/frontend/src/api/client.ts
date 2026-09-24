export type ModuleSummary = {
  id: string;
  name: string;
  status: string;
};


export async function listModules(): Promise<ModuleSummary[]> {
  const response = await fetch("/api/modules");
  if (!response.ok) {
    return [{ id: "home", name: "Home", status: "offline-preview" }];
  }
  return response.json() as Promise<ModuleSummary[]>;
}

