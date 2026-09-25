import type { Metadata } from "next";
// Self-hosted via npm (no build-time call to Google Fonts), so builds work offline and in CI.
import "@fontsource-variable/nunito";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Lingo",
  description: "Learn Spanish one bite-sized lesson at a time.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
