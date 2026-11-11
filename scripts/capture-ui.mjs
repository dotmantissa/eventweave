import { chromium } from "@playwright/test";
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
for (const [name, width, height, theme] of [
  ["desktop", 1440, 1050, "light"],
  ["mobile", 390, 1000, "light"],
  ["desktop-dark", 1440, 1050, "dark"],
]) {
  const page = await browser.newPage({
    viewport: { width, height },
    reducedMotion: "reduce",
  });
  await page.addInitScript(
    (t) => localStorage.setItem("eventweave.theme", t),
    theme,
  );
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", {
    waitUntil: "networkidle",
    timeout: 60000,
  });
  await page
    .locator(".loading-state")
    .waitFor({ state: "hidden", timeout: 60000 });
  await page.screenshot({
    path: ".impeccable/review/" + name + ".png",
    fullPage: true,
  });
  console.log(
    name,
    await page.title(),
    "horizontal overflow:",
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    "errors:",
    errors,
  );
  await page.close();
}
await browser.close();
