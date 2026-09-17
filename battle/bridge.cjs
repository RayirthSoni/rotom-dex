'use strict';
// One bounded JSON request on stdin; no web server, accounts, or battle rooms.
const {Dex, Teams, TeamValidator} = require('pokemon-showdown');
const {calculate, Pokemon, Move, Field} = require('@smogon/calc');
const readline = require('node:readline');
function handle(input) {
  const {operation} = input;
  if (operation === 'formats') return Dex.formats.all().filter(f => f.exists && f.name && f.mod && /^gen\d/.test(f.mod) && !f.effectType?.includes('Rule')).map(f => ({id:f.id,name:f.name,generation:Number(f.mod.match(/^gen(\d+)/)?.[1]),mod:f.mod,rules:f.ruleset||[],banlist:f.banlist||[],source:'https://github.com/smogon/pokemon-showdown',snapshot:require('pokemon-showdown/package.json').version}));
  if (operation === 'import') {const team=Teams.import(input.text); if (!team?.length) throw new Error('No Pokémon sets found. Paste a Showdown team.'); return {team};}
  if (operation === 'export') return {text:Teams.export(input.team)};
  if (operation === 'validate') {
    const format=Dex.formats.get(input.format);
    if (!format.exists || !/^gen\d/.test(format.mod)) throw new Error('Choose an exact supported competitive format.');
    const team=typeof input.team==='string' ? Teams.import(input.team) : input.team;
    if (!team?.length || team.length>6) throw new Error('Supply between one and six Pokémon.');
    const errors=new TeamValidator(format.id).validateTeam(team);
    return {format:format.id,valid:!errors,issues:errors||[],team,rules:format.ruleset,source:'https://github.com/smogon/pokemon-showdown',snapshot:require('pokemon-showdown/package.json').version,scope:'Competitive legality only; story acquisition is checked separately.'};
  }
  if (operation === 'damage') {
    const gen=Number(input.generation);
    if (!Number.isInteger(gen)||gen<1||gen>9) throw new Error('Damage calculation supports generations 1–9.');
    for (const set of [input.attacker,input.defender]) {
      if (!set || typeof set.species !== 'string') throw new Error('Both Pokémon need a species.');
      if (set.ivs && Object.values(set.ivs).some(v => !Number.isInteger(v)||v<0||v>31)) throw new Error('IVs must be between 0 and 31. For generations 1–2 the calculator converts them to DVs.');
      if (set.evs && Object.values(set.evs).reduce((a,b)=>a+b,0)>510 && gen>=3) throw new Error('EVs must total at most 510.');
      if (gen<3 && (set.ability||set.nature)) throw new Error('Abilities and natures do not apply before generation 3.');
      if (gen<9 && set.teraType) throw new Error('Terastallization requires generation 9.');
      if (gen!==8 && set.isDynamaxed) throw new Error('Dynamax requires generation 8.');
    }
    const attacker=new Pokemon(gen,input.attacker.species,input.attacker);
    const defender=new Pokemon(gen,input.defender.species,input.defender);
    const move=new Move(gen,input.move);
    const result=calculate(gen,attacker,defender,move,new Field(input.field||{}));
    return {generation:gen,range:result.range(),description:result.desc(),assumptions:'Default level 100 unless supplied; omitted EVs = 0, IVs = 31, neutral nature, no boosts, full HP, no weather or terrain. Species default abilities may apply. This is one move, not a prediction of the battle.',source:'https://github.com/smogon/damage-calc',snapshot:require('@smogon/calc/package.json').version};
  }
  throw new Error('Unknown battle operation.');
}
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
  try {process.stdout.write(JSON.stringify({ok:true,data:handle(JSON.parse(line))})+'\n');}
  catch(error) {process.stdout.write(JSON.stringify({ok:false,error:error.message})+'\n');}
});
