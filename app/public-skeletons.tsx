"use client";

type CountProps = {
  count?: number;
};

export function PublicListSkeleton({ count = 6 }: CountProps) {
  return (
    <section className="public-grid skeleton-grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <article className="skeleton-card" key={`skeleton-card-${index}`}>
          <div className="skeleton-media" />
          <div className="skeleton-line short" />
          <div className="skeleton-line title" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-row">
            <div className="skeleton-line short" />
            <div className="skeleton-line short" />
          </div>
        </article>
      ))}
    </section>
  );
}

export function PublicDetailSkeleton() {
  return (
    <section className="public-detail" aria-hidden="true">
      <div className="skeleton-media detail" />
      <article className="skeleton-card detail">
        <div className="skeleton-row">
          <div className="skeleton-line short" />
          <div className="skeleton-line short" />
        </div>
        <div className="skeleton-line title" />
        <div className="skeleton-line" />
        <div className="skeleton-line" />
        <div className="skeleton-line" />
      </article>
      <article className="skeleton-card detail">
        <div className="skeleton-line title" />
        <div className="skeleton-line" />
        <div className="skeleton-line" />
      </article>
    </section>
  );
}

