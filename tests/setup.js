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
global.fetch = jest.fn();

// Mock DOM elements
document.getElementById = jest.fn((id) => {
  const elements = {
    graph: {
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 1000, height: 800 }),
      data: [],
      _hoverdata: null,
      on: jest.fn(),
    },
    ctxMenu: { style: { display: 'none', left: '0px', top: '0px' } },
    ctxEditPerson: { style: { display: 'none' } },
    ctxAddPerson: { style: { display: 'none' } },
    ctxAddChildOf: { style: { display: 'none' } },
    ctxDeletePerson: { style: { display: 'none' } },
    ctxDeleteRelationship: { style: { display: 'none' } },
    relStatusText: { textContent: '' },
    draftCountBadge: { textContent: '0' },
    treeSelect: { innerHTML: '', appendChild: jest.fn(), parentNode: { insertBefore: jest.fn() } },
    personModal: { style: { display: 'none' }, dataset: {} },
    personModalBackdrop: { style: { display: 'none' } },
    personModalTitle: { textContent: '' },
    personNameInput: { value: '' },
    personNotesInput: { value: '' },
    personParentSelect: { innerHTML: '', appendChild: jest.fn(), value: '' },
    treeNameInput: { value: '' },
    treeVersionsSelect: { innerHTML: '', appendChild: jest.fn(), value: '' },
    treeLoadVersionBtn: { onclick: null },
    treeSaveBtn: { onclick: null },
    treeDiscardBtn: { onclick: null },
    treeNewBtn: { onclick: null },
    personModalSave: { addEventListener: jest.fn() },
    personModalCancel: { addEventListener: jest.fn() },
    personParentSave: { addEventListener: jest.fn() },
    ctxDeleteRelationship: { style: { display: 'none' }, addEventListener: jest.fn() },
    ctxDeletePerson: { addEventListener: jest.fn() },
    ctxEditPerson: { addEventListener: jest.fn() },
  };
  return elements[id] || null;
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
