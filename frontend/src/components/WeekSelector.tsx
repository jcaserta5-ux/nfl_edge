interface Props {
  week: number;
  onChange: (w: number) => void;
}

export function WeekSelector({ week, onChange }: Props) {
  const weeks = Array.from({ length: 18 }, (_, i) => i + 1);
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-400">Week</span>
      <select
        value={week}
        onChange={(e) => onChange(Number(e.target.value))}
        className="bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-emerald-500 outline-none"
      >
        {weeks.map((w) => (
          <option key={w} value={w}>
            {w === 1 ? 'Week 1' : `Week ${w}`}
          </option>
        ))}
        <option value={19}>Wild Card</option>
        <option value={20}>Divisional</option>
        <option value={21}>Conference</option>
        <option value={22}>Super Bowl</option>
      </select>
    </div>
  );
}
