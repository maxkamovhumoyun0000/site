import { expect, test } from "@playwright/test";

async function expectDesktopSidebarNotOverlapping(page: import("@playwright/test").Page) {
  const sidebar = page.getByTestId("desktop-sidebar");
  const workspace = page.getByTestId("workspace-shell");

  await expect(sidebar).toBeVisible();
  await expect(workspace).toBeVisible();

  const sidebarBox = await sidebar.boundingBox();
  const workspaceBox = await workspace.boundingBox();

  expect(sidebarBox).not.toBeNull();
  expect(workspaceBox).not.toBeNull();
  if (!sidebarBox || !workspaceBox) return;

  expect(sidebarBox.x + sidebarBox.width).toBeLessThanOrEqual(workspaceBox.x + 1);
}

test("public pages hide hero nav blocks", async ({ page }) => {
  await page.route("**/api/public/courses**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.goto("/courses");
  await expect(page.locator(".public-hero-no-nav")).toBeVisible();
  await expect(page.locator(".public-topbar")).toHaveCount(0);
  await expect(page.locator(".public-mobile-menu")).toHaveCount(0);
  await expect(page.locator(".public-bottom-nav")).toHaveCount(0);
});

test("dark theme keeps hero/card surfaces dark", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("diamond_theme", "dark");
  });

  await page.route("**/api/public/courses**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.goto("/courses");
  await page.waitForFunction(() => document.documentElement.getAttribute("data-theme") === "dark");

  const heroBgImage = await page.locator(".public-hero").evaluate((el) => getComputedStyle(el).backgroundImage || "");
  const cardBgColor = await page.locator(".panel-card").first().evaluate((el) => getComputedStyle(el).backgroundColor || "");

  expect(heroBgImage.toLowerCase()).toContain("gradient");
  expect(cardBgColor).not.toBe("rgb(255, 255, 255)");
});

test("dark theme keeps dashboard hero card non-white", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("diamond_theme", "dark");
    window.localStorage.setItem("diamond_token", "student-token");
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();

    if (url.includes("/api/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 11, login_type: 1, role: "student", full_name: "Student User", language: "uz" }),
      });
      return;
    }

    if (url.includes("/api/student/proctoring/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ face_enrollment_required: false, proctoring_required: false, blocked: false }),
      });
      return;
    }

    if (url.includes("/api/app/state")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          effective_role: "student",
          sections: {
            student: ["home", "homework", "profile"],
            teacher: ["home", "homework", "profile"],
            support: ["home", "profile"],
            admin: ["home", "holidays", "profile"],
          },
          student: {
            stats: {
              total_dcoin: 42.5,
              global_rank: 7,
            },
          },
        }),
      });
      return;
    }

    if (url.includes("/api/notifications/unread-count")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread_count: 0 }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/");
  await page.waitForFunction(() => document.documentElement.getAttribute("data-theme") === "dark");
  await expect(page.getByTestId("student-home-hero")).toBeVisible();
  await expectDesktopSidebarNotOverlapping(page);

  const heroCardBg = await page.getByTestId("student-home-hero").evaluate((el) => getComputedStyle(el).backgroundColor || "");
  expect(heroCardBg).not.toBe("rgb(255, 255, 255)");
});

test("student homework submit flow works", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("diamond_token", "student-token");
  });

  const studentHomeworks = [
    {
      id: 101,
      title: "Essay",
      description: "Write a short essay",
      due_at: "2026-04-30T10:00",
      submission_status: null,
      submission_note: null,
      proof_image_url: null,
      teacher_first_name: "Ali",
      teacher_last_name: "Teacher",
      dcoin_delta: 0,
      reviewed_at: null,
    },
  ];
  let submitPayload: any = null;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (url.includes("/api/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 11, login_type: 1, role: "student", full_name: "Student User", language: "uz" }),
      });
      return;
    }

    if (url.includes("/api/student/proctoring/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ face_enrollment_required: false, proctoring_required: false, blocked: false }),
      });
      return;
    }

    if (url.includes("/api/app/state")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          effective_role: "student",
          sections: {
            student: ["home", "homework", "profile"],
            teacher: ["home", "homework", "profile"],
            support: ["home", "profile"],
            admin: ["home", "holidays", "profile"],
          },
          student: {},
        }),
      });
      return;
    }

    if (url.includes("/api/notifications/unread-count")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread_count: 0 }) });
      return;
    }

    if (url.includes("/api/student/homework") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: studentHomeworks }),
      });
      return;
    }

    if (url.includes("/api/homework/upload-image") && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ url: "/uploads/student-proof.png" }),
      });
      return;
    }

    if (url.includes("/api/student/homework/101/submit") && method === "POST") {
      submitPayload = request.postDataJSON();
      studentHomeworks[0] = {
        ...studentHomeworks[0],
        submission_status: String(submitPayload?.status || "done"),
        submission_note: String(submitPayload?.note || ""),
        proof_image_url: String(submitPayload?.proof_image_url || ""),
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Homework submitted", submission: { id: "sub_1", ...submitPayload } }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/?section=homework");
  await expect(page.getByRole("heading", { name: "Mening Homeworklarim" })).toBeVisible();
  await expectDesktopSidebarNotOverlapping(page);

  const fileInput = page.locator("input[type='file']").first();
  await fileInput.setInputFiles({
    name: "proof.png",
    mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgo=", "base64"),
  });

  const firstHomeworkCard = page.locator("article.homework-card").first();
  await expect(firstHomeworkCard).toBeVisible();
  const submitButton = firstHomeworkCard.getByRole("button", { name: "Submit" });
  await submitButton.scrollIntoViewIfNeeded();
  await submitButton.click();
  await expect(page.getByText("Topshirildi. Teacher tekshiruviga yuborildi.")).toBeVisible();

  expect(submitPayload).toBeTruthy();
  expect(String(submitPayload.status)).toBe("done");
  expect(String(submitPayload.proof_image_url || "")).toContain("student-proof.png");
});

test("teacher homework review flow works", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("diamond_token", "teacher-token");
  });

  const teacherHomeworks = [
    {
      id: 201,
      title: "Grammar HW",
      description: "Review grammar",
      student_id: 11,
      student_first_name: "Student",
      student_last_name: "One",
      submission_student_id: 11,
      submission_status: "done",
      proof_image_url: "/uploads/hw-proof.png",
      reviewed_at: null,
      dcoin_delta: 0,
      group_id: null,
      group_name: null,
    },
  ];
  let reviewPayload: any = null;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (url.includes("/api/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 22, login_type: 3, login_id: "TCH001", role: "teacher", full_name: "Teacher User", language: "uz" }),
      });
      return;
    }

    if (url.includes("/api/app/state")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          effective_role: "teacher",
          sections: {
            student: ["home", "homework", "profile"],
            teacher: ["home", "homework", "groups", "profile"],
            support: ["home", "profile"],
            admin: ["home", "holidays", "profile"],
          },
          teacher: {},
        }),
      });
      return;
    }

    if (url.includes("/api/notifications/unread-count")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread_count: 0 }) });
      return;
    }

    if (url.includes("/api/teacher/homework") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: teacherHomeworks }),
      });
      return;
    }

    if (url.includes("/api/students") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [{ id: 11, full_name: "Student One" }] }),
      });
      return;
    }

    if (url.includes("/api/teacher/groups") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [{ id: 501, name: "Group A" }] }),
      });
      return;
    }

    if (url.includes("/api/teacher/homework/201/review") && method === "POST") {
      reviewPayload = request.postDataJSON();
      teacherHomeworks[0] = {
        ...teacherHomeworks[0],
        reviewed_at: "2026-04-24T10:00:00+00:00",
        dcoin_delta: Number(reviewPayload?.dcoin_delta || 0),
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Homework reviewed", submission: { id: 901, ...reviewPayload } }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/?section=homework");
  await expect(page.getByRole("heading", { name: "Teacher Homework" })).toBeVisible();

  const reviewTableRow = page.locator(".homework-review-table tbody tr").first();
  await reviewTableRow.locator("input[type='number']").first().fill("12");
  await reviewTableRow.locator("input[placeholder='review note']").first().fill("Good effort");
  await reviewTableRow.getByRole("button", { name: "Review" }).click();

  await expect(page.locator(".homework-review-table").getByText("Reviewed (12.0)").first()).toBeVisible();
  expect(reviewPayload).toBeTruthy();
  expect(Number(reviewPayload.dcoin_delta)).toBe(12);
  expect(String(reviewPayload.review_note)).toBe("Good effort");
});
