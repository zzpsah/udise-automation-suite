import "./styles.css";
export const metadata = { title: "UDISE Automation", description: "School UDISE automation control" };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
