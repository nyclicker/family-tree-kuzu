// Mock Plotly for unit tests
global.Plotly = {
  react: jest.fn().mockResolvedValue(undefined),
  newPlot: jest.fn().mockResolvedValue(undefined),
  restyle: jest.fn().mockResolvedValue(undefined),
  addTraces: jest.fn().mockResolvedValue([0]),
  deleteTraces: jest.fn().mockResolvedValue(undefined),
  Plots: {
    resize: jest.fn(),
  },
  Fx: {
    hover: jest.fn(),
    unhover: jest.fn(),
  },
};

// Mock fetch
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve([]),
    text: () => Promise.resolve(''),
  })
);

// Mock DOM elements
document.getElementById = jest.fn((id) => {
  const elements = {
    graph: {
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 1000, height: 800 }),
      data: [],
      _hoverdata: null,
      on: jest.fn(),
      addEventListener: jest.fn(),
    },
    ctxMenu: { style: { display: 'none', left: '0px', top: '0px' }, addEventListener: jest.fn() },
    ctxEditPerson: { style: { display: 'none' }, addEventListener: jest.fn(), onclick: null },
    ctxAddPerson: { style: { display: 'none' }, addEventListener: jest.fn(), onclick: null },
    ctxAddChildOf: { style: { display: 'none' }, addEventListener: jest.fn(), onclick: null },
    ctxDeletePerson: { style: { display: 'none' }, addEventListener: jest.fn(), onclick: null },
    ctxDeleteRelationship: { style: { display: 'none' }, addEventListener: jest.fn(), onclick: null },
    relStatusText: { textContent: '', addEventListener: jest.fn() },
    draftCountBadge: { textContent: '0', addEventListener: jest.fn() },
    treeSelect: { innerHTML: '', appendChild: jest.fn(), parentNode: { insertBefore: jest.fn() }, addEventListener: jest.fn() },
    personModal: { style: { display: 'none' }, dataset: {}, addEventListener: jest.fn() },
    personModalBackdrop: { style: { display: 'none' }, addEventListener: jest.fn() },
    personModalTitle: { textContent: '', addEventListener: jest.fn() },
    personNameInput: { value: '', addEventListener: jest.fn() },
    personNotesInput: { value: '', addEventListener: jest.fn() },
    personParentSelect: { innerHTML: '', appendChild: jest.fn(), value: '', addEventListener: jest.fn() },
    treeNameInput: { value: '', addEventListener: jest.fn() },
    treeVersionsSelect: { innerHTML: '', appendChild: jest.fn(), value: '', addEventListener: jest.fn() },
    treeLoadVersionBtn: { onclick: null, addEventListener: jest.fn() },
    treeSaveBtn: { onclick: null, addEventListener: jest.fn() },
    treeDiscardBtn: { onclick: null, addEventListener: jest.fn() },
    treeNewBtn: { onclick: null, addEventListener: jest.fn() },
    personModalSave: { addEventListener: jest.fn() },
    personModalCancel: { addEventListener: jest.fn() },
    personParentSave: { addEventListener: jest.fn() },
  };
  return elements[id] || { style: {}, addEventListener: jest.fn(), onclick: null };
});

document.createElement = jest.fn((tag) => ({
  value: '',
  textContent: '',
  style: {},
  appendChild: jest.fn(),
  addEventListener: jest.fn(),
}));

document.addEventListener = jest.fn();
window.addEventListener = jest.fn();
