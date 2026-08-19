'use client';

/** The user's question. The only bubble left on the page. */
export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[82%] rounded-[14px] rounded-br-[3px] bg-(--brand-primary) px-4 py-2.5 text-[14.5px] leading-snug whitespace-pre-wrap text-white">
        {text}
      </p>
    </div>
  );
}
