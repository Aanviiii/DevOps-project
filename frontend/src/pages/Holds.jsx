import { useState } from "react";
import { api } from "../api";
import { Async, Badge, EmptyState, Modal, useAction } from "../components/ui";
import { shortDate } from "../format";
import { useLoad } from "../hooks";
import { LendDialog } from "./Catalogue";

export default function Holds() {
  const [placing, setPlacing] = useState(false);
  const holds = useLoad(() => api.holds.list(), []);
  const act = useAction();

  const collect = async (hold) => {
    const ok = await act(
      () => api.loans.checkout(hold.book_id, hold.member_id),
      (loan) => `${loan.member_name} collected “${loan.book_title}”.`,
    );
    if (ok) holds.reload();
  };

  const cancel = async (hold) => {
    const ok = await act(
      () => api.holds.cancel(hold.id),
      () => `Cancelled ${hold.member_name}'s hold on “${hold.book_title}”.`,
    );
    if (ok) holds.reload();
  };

  return (
    <>
      <div className="toolbar">
        <p className="muted toolbar-note">
          A returned book is set aside for the first member in its queue, who has three days
          to collect it before it passes to the next.
        </p>
        <button className="button" onClick={() => setPlacing(true)}>
          + Place a hold
        </button>
      </div>

      <Async result={holds}>
        {(all) => {
          const ready = all.filter((h) => h.status === "READY");
          const waiting = all.filter((h) => h.status === "WAITING");
          return (
            <>
              <section className="section">
                <h2 className="section-title">
                  On the hold shelf <Badge tone="green">{ready.length}</Badge>
                </h2>
                {ready.length === 0 ? (
                  <EmptyState title="Nothing waiting to be collected" />
                ) : (
                  <div className="shelf-grid">
                    {ready.map((hold) => (
                      <article className="shelf-card" key={hold.id}>
                        <div>
                          <h3>{hold.book_title}</h3>
                          <p className="muted">for {hold.member_name}</p>
                        </div>
                        <Badge tone="amber">Collect by {shortDate(hold.ready_until)}</Badge>
                        <div className="card-actions">
                          <button className="button button-small" onClick={() => collect(hold)}>
                            Lend now
                          </button>
                          <button className="button button-small button-ghost danger" onClick={() => cancel(hold)}>
                            Cancel
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="section">
                <h2 className="section-title">
                  Waiting in the queue <Badge>{waiting.length}</Badge>
                </h2>
                {waiting.length === 0 ? (
                  <EmptyState title="No one is waiting">Holds appear here when every copy of a book is out.</EmptyState>
                ) : (
                  <div className="table-card">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Place</th>
                          <th>Book</th>
                          <th>Member</th>
                          <th>Since</th>
                          <th className="actions-col">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {waiting.map((hold) => (
                          <tr key={hold.id}>
                            <td data-label="Place">
                              <span className="queue-number">#{hold.queue_position}</span>
                            </td>
                            <td data-label="Book">
                              <strong>{hold.book_title}</strong>
                            </td>
                            <td data-label="Member">{hold.member_name}</td>
                            <td data-label="Since">{shortDate(hold.placed_at)}</td>
                            <td className="actions-col">
                              <button className="button button-small button-ghost danger" onClick={() => cancel(hold)}>
                                Cancel
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          );
        }}
      </Async>

      {placing && (
        <Modal title="Place a hold" onClose={() => setPlacing(false)} wide>
          <LendDialog
            mode="hold"
            onCancel={() => setPlacing(false)}
            onDone={() => {
              setPlacing(false);
              holds.reload();
            }}
          />
        </Modal>
      )}
    </>
  );
}
