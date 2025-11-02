// summarize budgets: warn >= 90%, breach > 100%
export function summarizeBudgetAlerts(clients = [], budgets = {}) {
  let breach = 0, warn = 0, ok = 0;

  for (const c of clients) {
    const name = c.client;
    const cost = Number(c.cost || 0);
    const budget = Number(budgets?.[name] ?? 0);
    if (!budget || budget <= 0) continue;

    const ratio = cost / budget;
    if (ratio > 1.0) breach++;
    else if (ratio >= 0.9) warn++;
    else ok++;
  }
  return { breach, warn, ok };
}
