import { useState } from "react";
import { api } from "../api";
import { Async, Badge, EmptyState, Field, Loading, ErrorState, Modal, useAction } from "../components/ui";
import { longDate, plural, rupees, shortDate, tierLabel } from "../format";
import { useDebounced, useLoad } from "../hooks";

const TIERS = ["", "STUDENT", "FACULTY", "PUBLIC"];

function NewMemberForm({ onDone, onCancel }) {
  const [form, setForm] = useState({ full_name: "", email: "", tier: "STUDENT" });
  const act = useAction();
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (event) => {
    event.preventDefault();
    const ok = await act(
      () => api.members.create(form),
      (m) => `Welcome, ${m.full_name}! Card ${m.card_number} issued.`,
    );
    if (ok) onDone();
  };

  return (
    <form className="form" onSubmit={submit}>
      <Field label="Full name">
        <input required minLength={2} maxLength={120} value={form.full_name} onChange={set("full_name")} />
      </Field>
      <Field label="Email">
        <input type="email" required value={form.email} onChange={set("email")} />
      </Field>
      <Field label="Membership" hint="Sets loan length, how many books at once, renewals and fine rates">
        <select value={form.tier} onChange={set("tier")}>
          {TIERS.slice(1).map((t) => (
            <option key={t} value={t}>
              {tierLabel[t]}
            </option>
          ))}
        </select>
      </Field>
      <div className="form-actions">
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className="button">Issue library card</button>
      </div>
    </form>
  );
}

function Account({ memberId, onChanged }) {
  const account = useLoad(() => api.members.account(memberId), [memberId]);
  const act = useAction();

  if (account.loading && !account.data) return <Loading />;
  if (account.error) return <ErrorState error={account.error} onRetry={account.reload} />;

  const { member, policy, active_loans: loans, holds, outstanding_fines: fines } = account.data;
  const refresh = () => {
    account.reload();
    onChanged();
  };

  const settle = async () => {
    if (await act(() => api.members.settleFines(member.id), (r) => `Recorded payment of ${rupees(r.settled)}.`)) refresh();
  };
  const toggleActive = async () => {
    const ok = await act(
      () => api.members.update(member.id, { active: !member.active }),
      (m) => `${m.full_name} is now ${m.active ? "active" : "suspended"}.`,
    );
    if (ok) refresh();
  };

  return (
    <div className="account">
      <div className="account-head">
        <div>
          <p className="muted">
            {member.card_number} · {member.email} · member since {longDate(member.joined_on)}
          </p>
          <div className="book-meta">
            <Badge tone="ink">{tierLabel[member.tier]}</Badge>
            {member.active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Suspended</Badge>}
            {account.data.can_borrow ? <Badge tone="green">Can borrow</Badge> : <Badge tone="amber">Borrowing blocked</Badge>}
          </div>
        </div>
      </div>

      <dl className="policy">
        <div>
          <dt>Loan period</dt>
          <dd>{policy.loan_days} days</dd>
        </div>
        <div>
          <dt>Books at once</dt>
          <dd>
            {loans.length} / {policy.max_active_loans}
          </dd>
        </div>
        <div>
          <dt>Renewals</dt>
          <dd>{policy.max_renewals} per loan</dd>
        </div>
        <div>
          <dt>Late fee</dt>
          <dd>
            {rupees(policy.fine_per_day)}/day after {plural(policy.grace_days, "day")}
          </dd>
        </div>
      </dl>

      <div className={`fines ${fines > 0 ? "fines-owed" : ""}`}>
        <div>
          <span className="muted">Outstanding fines</span>
          <strong>{rupees(fines)}</strong>
        </div>
        <button className="button button-small" disabled={fines === 0} onClick={settle}>
          Record payment
        </button>
      </div>

      <h3 className="subhead">Books out</h3>
      {loans.length === 0 ? (
        <p className="muted">No books on loan.</p>
      ) : (
        <ul className="plain-list">
          {loans.map((loan) => (
            <li key={loan.id}>
              <span>{loan.book_title}</span>
              {loan.days_overdue > 0 ? (
                <Badge tone="red">{plural(loan.days_overdue, "day")} late</Badge>
              ) : (
                <Badge tone="green">Due {shortDate(loan.due_on)}</Badge>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3 className="subhead">Holds</h3>
      {holds.length === 0 ? (
        <p className="muted">No holds.</p>
      ) : (
        <ul className="plain-list">
          {holds.map((hold) => (
            <li key={hold.id}>
              <span>{hold.book_title}</span>
              {hold.status === "READY" ? (
                <Badge tone="amber">Ready until {shortDate(hold.ready_until)}</Badge>
              ) : (
                <Badge>#{hold.queue_position} in queue</Badge>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="form-actions">
        <button className="button button-secondary" onClick={toggleActive}>
          {member.active ? "Suspend membership" : "Reactivate membership"}
        </button>
      </div>
    </div>
  );
}

export default function Members() {
  const [query, setQuery] = useState("");
  const [tier, setTier] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const q = useDebounced(query);
  const members = useLoad(() => api.members.list({ q, tier }), [q, tier]);

  return (
    <>
      <div className="toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search name, email or card number"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search members"
        />
        <div className="segmented" role="tablist" aria-label="Membership tier">
          {TIERS.map((t) => (
            <button key={t || "all"} role="tab" aria-selected={tier === t} className={tier === t ? "is-active" : ""} onClick={() => setTier(t)}>
              {t ? tierLabel[t] : "All"}
            </button>
          ))}
        </div>
        <button className="button" onClick={() => setCreating(true)}>
          + New member
        </button>
      </div>

      <Async result={members} empty={<EmptyState title="No members found" />}>
        {(list) => (
          <div className="table-card">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Card</th>
                  <th>Tier</th>
                  <th>Status</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {list.map((m) => (
                  <tr
                    key={m.id}
                    className="clickable"
                    tabIndex={0}
                    onClick={() => setSelected(m)}
                    onKeyDown={(e) => e.key === "Enter" && setSelected(m)}
                  >
                    <td data-label="Name">
                      <strong>{m.full_name}</strong>
                    </td>
                    <td data-label="Card" className="mono">
                      {m.card_number}
                    </td>
                    <td data-label="Tier">{tierLabel[m.tier]}</td>
                    <td data-label="Status">
                      {m.active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Suspended</Badge>}
                    </td>
                    <td data-label="Joined">{longDate(m.joined_on)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Async>

      {creating && (
        <Modal title="New member" onClose={() => setCreating(false)}>
          <NewMemberForm
            onCancel={() => setCreating(false)}
            onDone={() => {
              setCreating(false);
              members.reload();
            }}
          />
        </Modal>
      )}
      {selected && (
        <Modal title={selected.full_name} onClose={() => setSelected(null)} wide>
          <Account memberId={selected.id} onChanged={members.reload} />
        </Modal>
      )}
    </>
  );
}
