import "./styles.css";
export const metadata = { title: "UDISE Operations Console", description: "Private Hermes VPS workflow console for UDISE operations" };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
