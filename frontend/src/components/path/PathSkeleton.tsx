export function PathSkeleton() {
  return (
    <div className="mx-auto w-full max-w-xl animate-pulse space-y-12 px-4 py-8">
      {/* Unit Header Skeleton */}
      <div className="rounded-3xl border-2 border-line bg-canvas p-6">
        <div className="h-4 w-24 rounded-full bg-line" />
        <div className="mt-3 h-8 w-48 rounded-xl bg-line" />
        <div className="mt-2 h-4 w-72 rounded-full bg-line" />
      </div>

      {/* Path Nodes Skeleton */}
      <div className="flex flex-col items-center space-y-10 py-6">
        <div className="h-20 w-20 rounded-full bg-line" />
        <div className="h-20 w-20 translate-x-10 rounded-full bg-line" />
        <div className="h-20 w-20 rounded-full bg-line" />
        <div className="h-20 w-20 -translate-x-10 rounded-full bg-line" />
        <div className="h-20 w-20 rounded-full bg-line" />
      </div>
    </div>
  );
}
