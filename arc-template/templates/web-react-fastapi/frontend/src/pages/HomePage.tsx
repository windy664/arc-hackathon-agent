import { Activity, Database, LayoutDashboard, Workflow } from "lucide-react";
import { useEffect, useState } from "react";

import { listModules, type ModuleSummary } from "../api/client";


const cards = [
  { label: "Pages", value: "Ready", icon: LayoutDashboard },
  { label: "Data", value: "Seeded", icon: Database },
  { label: "Logic", value: "TDD", icon: Workflow },
  { label: "Status", value: "Preview", icon: Activity },
];


export default function HomePage() {
  const [modules, setModules] = useState<ModuleSummary[]>([]);

  useEffect(() => {
    listModules().then(setModules).catch(() => {
      setModules([{ id: "home", name: "Home", status: "offline-preview" }]);
    });
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 p-7 text-slate-900">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <p className="mb-1.5 text-xs font-bold uppercase text-blue-600">
            Generation Template
          </p>
          <h1 className="text-4xl font-bold">Generated Application</h1>
        </div>
      </header>
      <section className="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article
              className="grid gap-2 rounded-lg border border-slate-200 bg-white p-5"
              key={card.label}
            >
              <Icon aria-hidden="true" className="text-blue-600" />
              <span className="text-sm text-slate-500">{card.label}</span>
              <strong className="text-2xl">{card.value}</strong>
            </article>
          );
        })}
      </section>
      <section className="grid grid-cols-1 gap-5 rounded-lg border border-slate-200 bg-white p-5 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-xl font-semibold">Modules</h2>
          <ul className="m-0 list-none p-0">
            {modules.map((module) => (
              <li
                className="flex justify-between gap-3 border-b border-slate-100 py-2.5"
                key={module.id}
              >
                <span>{module.name}</span>
                <small className="text-slate-500">{module.status}</small>
              </li>
            ))}
          </ul>
        </aside>
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-xl font-semibold">Implementation Area</h2>
          <p className="max-w-2xl leading-7 text-slate-600">
            Generation agents should replace this starter view with pages, forms,
            data models, and workflows derived from the active requirement module.
          </p>
        </section>
      </section>
    </main>
  );
}

