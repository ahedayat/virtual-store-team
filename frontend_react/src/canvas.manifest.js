export const manifest = {
  screens: {
    scr_12zbnk: { name: "داشبورد", route: "/dashboard", position: { "x": 0, "y": 0 }, isDefaultRow: true },
    scr_pfmgba: { name: "عامل محتوا", route: "/content-agent", position: { "x": 160, "y": 1820 } },
    scr_dfy45q: { name: "ساخت محتوای جدید", route: "/content-agent/new-content", position: { "x": 1560, "y": 1820 } },
    scr_41mzac: { name: "عامل فروش", route: "/sales-agent", position: { "x": 1400, "y": 0 }, isDefaultRow: true },
    scr_xxzx2l: { name: "عامل پشتیبانی", route: "/support-agent", position: { "x": 2800, "y": 0 }, isDefaultRow: true },
    scr_dl22ry: { name: "عامل هماهنگ‌کننده", route: "/coordinator-agent", position: { "x": 4200, "y": 0 }, isDefaultRow: true }
  },
  sections: {
    sec_gb3x8b: { name: "Content Agent Flow", x: 0, y: 1600, width: 2920, height: 1180 }
  },
  layers: [
  { kind: "screen", id: "scr_12zbnk" },
  { kind: "screen", id: "scr_41mzac" },
  { kind: "screen", id: "scr_xxzx2l" },
  { kind: "screen", id: "scr_dl22ry" },
  { kind: "section", id: "sec_gb3x8b", children: [
    { kind: "screen", id: "scr_pfmgba" },
    { kind: "screen", id: "scr_dfy45q" }]
  }]

};