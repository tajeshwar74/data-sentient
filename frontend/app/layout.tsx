import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Sentient",
  description: "A thoughtful workspace for your data pipelines.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
