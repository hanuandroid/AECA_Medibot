import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediBot",
  description: "MediAssist Health Network knowledge assistant with role-based access control",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
