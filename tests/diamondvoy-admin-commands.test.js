const test = require("node:test");
const assert = require("node:assert/strict");

const {
  diamondvoyAdminCommandForInput,
  shouldShowDiamondvoyAdminCommands,
} = require("../app/ui/diamondvoy-admin-commands");

test("recognises the existing-chat student import slash commands", () => {
  assert.equal(diamondvoyAdminCommandForInput("/oquvchi-qoshish"), "add_students");
  assert.equal(diamondvoyAdminCommandForInput("/add-students"), "add_students");
});

test("shows command suggestions only after a slash is typed", () => {
  assert.equal(shouldShowDiamondvoyAdminCommands("/"), true);
  assert.equal(shouldShowDiamondvoyAdminCommands("  /add"), true);
  assert.equal(shouldShowDiamondvoyAdminCommands("Yangi oquvchi"), false);
});
