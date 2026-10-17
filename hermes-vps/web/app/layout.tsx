import "./styles.css";
import { APP_RELEASE } from "./release";
export const metadata = { title: `UDISE Operations Console · v${APP_RELEASE.version}`, description: `UDISE Operations Console, release v${APP_RELEASE.version} dated ${APP_RELEASE.date}` };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
