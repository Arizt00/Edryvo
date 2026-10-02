// Run this file with the Node.js runtime selected in the toolbar.
const project = { name: 'Lumen', languages: ['JavaScript', 'Python', 'C', 'C++', 'ASM'] };
console.log(`${project.name} · a brighter workflow`);
console.table(project.languages.map((language, index) => ({ id: index + 1, language })));
