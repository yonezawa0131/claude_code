const dateFormatter = new Intl.DateTimeFormat('ja-JP', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  timeZone: 'Asia/Tokyo',
});

export function formatDate(date: Date): string {
  return dateFormatter.format(date);
}
