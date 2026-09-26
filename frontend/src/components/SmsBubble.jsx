// Phone-style message bubble. The only rounded element in the app, on purpose:
// it imitates a messaging app, not the case-file UI around it.
export default function SmsBubble({ sender, time, text }) {
  return (
    <div className="mx-auto w-full max-w-sm border border-rule bg-sheet">
      <div className="border-b border-rule px-4 py-2 text-center">
        <div className="font-mono text-sm font-medium">{sender}</div>
        <div className="text-[11px] text-muted">Text message · Today {time}</div>
      </div>
      <div className="px-4 py-5">
        <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-rule/70 px-3.5 py-2.5 text-[15px] leading-snug">
          {text}
        </div>
        <div className="mt-1 pl-1 text-[11px] text-muted">{time}</div>
      </div>
    </div>
  )
}
