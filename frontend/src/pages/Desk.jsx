import { useState } from "react";
import { api } from "../api";
import { Async, Badge, EmptyState, Modal, useAction } from "../components/ui";
import { plural, rupees, shortDate } from "../format";
import { useLoad } from "../hooks";
import { LendDialog } from "./Catalogue";

const FILTERS = [
  { key: "active", label: "On loan" },
  { key: "overdue", label: "Overdue" },
  { key: "returned", label: "Returned" },
];

function DueBadge({ loan }) {
  if (loan.returned_on) {
    return loan.fine_due > 0 ? (
      <Badge tone={loan.fine_settled_on ? "neutral" : "red"}>
        {rupees(loan.fine_due)} {loan.fine_settled_on ? "paid" : "owed"}
      </Badge>
    ) : (
      <Badge tone="green">On time</Badge>
    );
  }
  if (loan.days_overdue > 0) {
    return (
      <Badge tone="red">
        {plural(loan.days_overdue, "day")} late
        {loan.fine_due > 0 ? ` · ${rupees(loan.fine_due)}` : ""}
      </Badge>
    );
  }
  return <Badge tone="green">Due {shortDate(loan.due_on)}</Badge>;
}

export default function Desk() {
  const [filter, setFilter] = useState("active");
  const [lending, setLending] = useState(false);
  const loans = useLoad(() => api.loans.list({ state: filter }), [filter]);
  const act = useAction();

  const giveBack = async (loan) => {
    const ok = await act(
      () => api.loans.giveBack(loan.id),
      (l) =>
        l.fine_due > 0
          ? `Returned “${l.book_title}”. Fine charged: ${rupees(l.fine_due)}.`
          : `Returned “${l.book_title}” on time.`,
    );
    if (ok) loans.reload();
  };

  const renew = async (loan) => {
    const ok = await act(
      () => api.loans.renew(loan.id),
      (l) => `Renewed “${l.book_title}” until ${shortDate(l.due_on)}.`,
    );
    if (ok) loans.reload();
  };

  return (
    <>
      <div className="toolbar">
        <div className="segmented" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              role="tab"
              aria-selected={filter === f.key}
              className={filter === f.key ? "is-active" : ""}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button className="button" onClick={() => setLending(true)}>
          + Lend a book
        </button>
      </div>

      <Async
        result={loans}
        empty={
          <EmptyState title={filter === "overdue" ? "Nothing overdue" : "No loans here"}>
            {filter === "overdue" ? "Every borrowed book is within its loan period." : null}
          </EmptyState>
        }
      >
        {(list) => (
          <div className="table-card">
            <table className="table">
              <thead>
                <tr>
                  <th>Book</th>
                  <th>Member</th>
                  <th>Lent</th>
                  <th>{filter === "returned" ? "Returned" : "Due"}</th>
                  <th>Status</th>
                  {filter !== "returned" && <th className="actions-col">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {list.map((loan) => (
                  <tr key={loan.id} className={loan.days_overdue > 0 && !loan.returned_on ? "row-alert" : ""}>
                    <td data-label="Book">
                      <span>
                        <strong>{loan.book_title}</strong>
                        {loan.renewals > 0 && <small className="muted"> · renewed {loan.renewals}×</small>}
                      </span>
                    </td>
                    <td data-label="Member">{loan.member_name}</td>
                    <td data-label="Lent">{shortDate(loan.checked_out_on)}</td>
                    <td data-label={filter === "returned" ? "Returned" : "Due"}>
                      {shortDate(loan.returned_on ?? loan.due_on)}
                    </td>
                    <td data-label="Status">
                      <DueBadge loan={loan} />
                    </td>
                    {filter !== "returned" && (
                      <td className="actions-col">
                        <button className="button button-small" onClick={() => giveBack(loan)}>
                          Return
                        </button>
                        <button className="button button-small button-ghost" onClick={() => renew(loan)}>
                          Renew
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Async>

      {lending && (
        <Modal title="Lend a book" onClose={() => setLending(false)} wide>
          <LendDialog
            mode="lend"
            onCancel={() => setLending(false)}
            onDone={() => {
              setLending(false);
              loans.reload();
            }}
          />
        </Modal>
      )}
    </>
  );
}
