const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const longDateFormat = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

// API dates are plain YYYY-MM-DD; parse them as local dates so they never shift a day.
const parseDay = (iso) => {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
};

export const shortDate = (iso) => (iso ? dateFormat.format(parseDay(iso)) : "—");
export const longDate = (iso) => (iso ? longDateFormat.format(parseDay(iso)) : "—");
export const rupees = (amount) => `₹${Number(amount ?? 0).toLocaleString("en-IN")}`;

export const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

export const tierLabel = { STUDENT: "Student", FACULTY: "Faculty", PUBLIC: "Public" };

// A stable colour for each book cover, derived from its title.
const COVER_HUES = [152, 18, 38, 205, 280, 345, 95, 190];
export function coverHue(title) {
  let hash = 0;
  for (const ch of title) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return COVER_HUES[hash % COVER_HUES.length];
}

export const initials = (text) =>
  text
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w))
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
