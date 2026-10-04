import { useMemo, useState } from 'react';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

export default function WeekdayPicker({ value = [], onChange }) {
  const now = new Date();
  const [view, setView] = useState(() => new Date(now.getFullYear(), now.getMonth(), 1));
  const days = useMemo(() => {
    const year = view.getFullYear();
    const month = view.getMonth();
    const offset = (new Date(year, month, 1).getDay() || 7) - 1;
    const count = new Date(year, month + 1, 0).getDate();
    const cells = Array.from({ length: offset }, () => null);
    for (let day = 1; day <= count; day++) cells.push(new Date(year, month, day));
    return cells;
  }, [view]);
  const selected = new Set(value);

  const toggle = iso => {
    const next = new Set(selected);
    if (next.has(iso)) next.delete(iso);
    else next.add(iso);
    onChange([...next].sort());
  };

  return (
    <div className="max-w-sm rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <button type="button" aria-label="Previous month" onClick={() => setView(d => new Date(d.getFullYear(), d.getMonth() - 1, 1))} className="rounded-md px-2 py-1 text-gray-500 hover:bg-gray-100">‹</button>
        <span className="text-sm font-semibold text-gray-800">
          {view.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </span>
        <button type="button" aria-label="Next month" onClick={() => setView(d => new Date(d.getFullYear(), d.getMonth() + 1, 1))} className="rounded-md px-2 py-1 text-gray-500 hover:bg-gray-100">›</button>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {DAY_NAMES.map(name => <span key={name} className="py-1 text-center text-xs font-medium text-gray-400">{name.slice(0, 2)}</span>)}
        {days.map((date, index) => {
          if (!date) return <span key={`empty-${index}`} />;
          const iso = isoDate(date);
          const active = selected.has(iso);
          const today = iso === isoDate(new Date());
          return (
            <button key={iso} type="button" aria-pressed={active} onClick={() => toggle(iso)}
              className={`h-9 rounded-lg text-sm font-medium transition ${active ? 'bg-teal-500 text-white shadow-sm' : 'text-gray-700 hover:bg-teal-50'} ${today && !active ? 'ring-2 ring-teal-200' : ''}`}>
              {date.getDate()}
            </button>
          );
        })}
      </div>
      <p className="mt-3 border-t pt-2 text-xs text-gray-500">Selected dates send at the same time: <strong className="text-gray-700">{value.length || 'none'}</strong></p>
    </div>
  );
}
