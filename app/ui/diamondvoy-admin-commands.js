const addStudentsCommands = new Set([
  "/oquvchi-qoshish",
  "/o‘quvchi-qo‘shish",
  "/add-students",
]);

function diamondvoyAdminCommandForInput(value) {
  const input = String(value || "").trim().toLowerCase();
  return addStudentsCommands.has(input) ? "add_students" : null;
}

function shouldShowDiamondvoyAdminCommands(value) {
  return String(value || "").trimStart().startsWith("/");
}

module.exports = {
  diamondvoyAdminCommandForInput,
  shouldShowDiamondvoyAdminCommands,
};
