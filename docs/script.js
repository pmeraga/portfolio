// Real demonstration pair from the included ARC puzzle 007bbfb7.
const example = {"input": [[0, 7, 7], [7, 7, 7], [0, 7, 7]], "output": [[0, 0, 0, 0, 7, 7, 0, 7, 7], [0, 0, 0, 7, 7, 7, 7, 7, 7], [0, 0, 0, 0, 7, 7, 0, 7, 7], [0, 7, 7, 0, 7, 7, 0, 7, 7], [7, 7, 7, 7, 7, 7, 7, 7, 7], [0, 7, 7, 0, 7, 7, 0, 7, 7], [0, 0, 0, 0, 7, 7, 0, 7, 7], [0, 0, 0, 7, 7, 7, 7, 7, 7], [0, 0, 0, 0, 7, 7, 0, 7, 7]]};
const colors = ["#0a1322", "#358cf5", "#ee534d", "#5ec883", "#f3d15c", "#9ca5af", "#dc61c5", "#efab5c", "#61d7df", "#ad4f51"];
for (const key of ["input", "output"]) {
  const grid = document.getElementById(`arc-${key}`);
  grid.style.gridTemplateColumns = `repeat(${example[key][0].length}, 1fr)`;
  for (const row of example[key]) for (const color of row) {
    const cell = document.createElement("span");
    cell.className = "arc-cell";
    cell.style.backgroundColor = colors[color];
    grid.appendChild(cell);
  }
}
