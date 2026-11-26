// Figures candlestick (bibliothèque cm45t3r/candlestick, copiée dans vendor/) sur un fichier de bougies JSON.
// Pas de résolution des conflits : elle supprime une figure à cause de la bougie suivante (information future).
// Sortie : une ligne par figure, indexée sur sa DERNIÈRE bougie (celle où la figure est visible) : index,direction
const lib = require("./vendor/candlestick");
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const res = lib.patternChain(data, lib.allPatterns, { trendContext: { trendMethod: "sma-slope", trendPeriod: 10, resolveConflicts: false } });
for (const r of res) {
  const n = Array.isArray(r.match) ? r.match.length : 1;
  const md = lib.metadata.getPatternMetadata(r.pattern) || {};
  if (md.direction === "bullish" || md.direction === "bearish") console.log(`${r.index + n - 1},${md.direction},${r.pattern}`);
}
