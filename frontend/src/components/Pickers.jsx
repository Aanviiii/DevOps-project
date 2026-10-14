import { useState } from "react";
import { api } from "../api";
import { useDebounced, useLoad } from "../hooks";
import { tierLabel } from "../format";

// A search box over a list of options, rendered as a listbox of radio-like rows.
function SearchPicker({ placeholder, load, render, value, onChange, deps }) {
  const [query, setQuery] = useState("");
  const q = useDebounced(query);
  const options = useLoad(() => load(q), [q, ...deps]);

  return (
    <div className="picker">
      <input
        type="search"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="picker-options" role="listbox">
        {options.loading && !options.data && <div className="picker-empty">Searching…</div>}
        {options.error && <div className="picker-empty">{options.error.message}</div>}
        {options.data?.length === 0 && <div className="picker-empty">No matches</div>}
        {options.data?.map((option) => (
          <button
            type="button"
            role="option"
            aria-selected={value?.id === option.id}
            key={option.id}
            className={`picker-option ${value?.id === option.id ? "is-selected" : ""}`}
            onClick={() => onChange(option)}
          >
            {render(option)}
          </button>
        ))}
      </div>
    </div>
  );
}

export function MemberPicker({ value, onChange }) {
  return (
    <SearchPicker
      placeholder="Search members by name, email or card"
      load={(q) => api.members.list({ q, active: true })}
      deps={[]}
      value={value}
      onChange={onChange}
      render={(m) => (
        <>
          <span>{m.full_name}</span>
          <small>
            {m.card_number} · {tierLabel[m.tier]}
          </small>
        </>
      )}
    />
  );
}

export function BookPicker({ value, onChange }) {
  return (
    <SearchPicker
      placeholder="Search books by title, author or ISBN"
      load={(q) => api.books.list({ q, limit: 30 })}
      deps={[]}
      value={value}
      onChange={onChange}
      render={(b) => (
        <>
          <span>{b.title}</span>
          <small>
            {b.author} · {b.copies_available > 0 ? `${b.copies_available} on shelf` : "all out"}
          </small>
        </>
      )}
    />
  );
}
