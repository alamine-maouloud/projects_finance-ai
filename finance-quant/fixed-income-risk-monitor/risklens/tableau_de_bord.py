"""Tableau de bord HTML autonome : un seul fichier, sans dépendance externe, utilisable hors ligne.

Les données du moteur sont embarquées en JSON ; les calculs interactifs (confiance, vente,
stress) sont refaits dans le navigateur avec les mêmes formules que le moteur Python.
La concordance est vérifiée par risklens.verification_tableau.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .donnees import ACTIF_NET_FONDS, DATE_REFERENCE, charger_manifeste
from .stress import SCENARIOS_TYPES


def donnees_tableau(res: dict) -> dict:
    pf, sc = res["portefeuille"], res["scenarios"]
    manifeste = charger_manifeste()
    positions = [dict(
        isin=p.isin, libelle=p.ligne.libelle, emetteur=p.ligne.emetteur, echeance=p.ligne.echeance.isoformat(),
        coupon=p.ligne.coupon, valeur=p.ligne.valeur, prix=p.ligne.prix_clean, dirty=p.ligne.prix_dirty,
        spread=p.calibration.spread, krd=list(p.sensibilites), ds=p.duration_spread, beta=p.beta_spread,
        flux=[[f.t, f.valeur_actuelle] for f in p.calibration.flux]) for p in pf.positions]
    alertes = sorted(res["alertes"], key=lambda a: ["À instruire", "À examiner", "Information"].index(a.severite))
    return dict(
        meta=dict(fonds="R-co Conviction Credit Euro", date=DATE_REFERENCE.isoformat(), actif_net=ACTIF_NET_FONDS,
                  valeur=pf.valeur_totale, lignes=len(positions), inventaire=len(res["inventaire"]),
                  spread=res["spread_raccorde"], methode=res["methode_spread"], spread_reference=res["spread_reference"],
                  genere=datetime.now(timezone.utc).strftime("%d/%m/%Y"), vente_isin=res["isin_vente"],
                  vente_montant=res["montant_vente"]),
        positions=positions,
        scenarios=dict(dates=[s.date.isoformat() for s in sc], d2=[s.variations[0] for s in sc],
                       d5=[s.variations[1] for s in sc], d10=[s.variations[2] for s in sc],
                       ds=[s.variation_spread for s in sc]),
        presets={k: list(v) for k, v in SCENARIOS_TYPES.items()},
        alertes=[a.__dict__ for a in alertes],
        exclusions=[dict(isin=l.isin, libelle=l.libelle, motifs=m) for l, m in res["exclues"]],
        rapprochements=[dict(libelle=l, obtenu=o, attendu=a, ok=ok) for l, o, a, ok in res["rapprochements"]],
        indisponibles=[dict(theme=t, constat=c, suite=s) for t, c, s in res["indisponibles"]],
        sources=[dict(nom=v["description"], url=v["url"], sha256=v["sha256"], present=v["present"])
                 for v in manifeste["sources"].values()],
        empreintes=res["empreintes"],
    )


def generer_tableau(chemin: Path, res: dict) -> None:
    donnees = json.dumps(donnees_tableau(res), ensure_ascii=False, separators=(",", ":"))
    donnees = donnees.replace("</", "<\\/")
    Path(chemin).write_text(GABARIT.replace("__DONNEES__", donnees), encoding="utf-8")


GABARIT = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>RiskLens : risque d'une poche obligataire publiée</title>
<style>
:root{
  --paper:#eef1f4; --surface:#ffffff; --ink:#172331; --muted:#566778; --rule:#cfd7df; --rule-soft:#e3e8ed;
  --t2:#a9c0d8; --t5:#5d87b4; --t10:#2f5d8c; --credit:#3f7f6e; --alerte:#b3261e; --examen:#94610a;
  --alerte-fond:#f8e1df; --examen-fond:#f6ecd9; --info-fond:#e4ebf2; --focus:#2f5d8c;
  --serif:"Iowan Old Style","Charter","Palatino Linotype","Book Antiqua",Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0f171f; --surface:#16212c; --ink:#e5ecf2; --muted:#9aabbb; --rule:#2b3a48; --rule-soft:#223140;
    --t2:#3d5a78; --t5:#5f8bbb; --t10:#9cc0e4; --credit:#6fb7a2; --alerte:#f2877e; --examen:#e0b062;
    --alerte-fond:#3a1f1d; --examen-fond:#352a17; --info-fond:#1e2c3a; --focus:#9cc0e4; color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --paper:#0f171f; --surface:#16212c; --ink:#e5ecf2; --muted:#9aabbb; --rule:#2b3a48; --rule-soft:#223140;
  --t2:#3d5a78; --t5:#5f8bbb; --t10:#9cc0e4; --credit:#6fb7a2; --alerte:#f2877e; --examen:#e0b062;
  --alerte-fond:#3a1f1d; --examen-fond:#352a17; --info-fond:#1e2c3a; --focus:#9cc0e4; color-scheme:dark;
}
:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*,*::before,*::after{box-sizing:inherit}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans);font-variant-numeric:tabular-nums;
  padding-left:env(safe-area-inset-left,0px);padding-right:env(safe-area-inset-right,0px)}
.page{max-width:1180px;margin:0 auto;padding:28px 24px 64px}
h1,h2,h3{font-family:var(--serif);font-weight:600;margin:0;letter-spacing:-0.01em}
h1{font-size:30px;line-height:1.15}
h2{font-size:21px;margin-bottom:10px}
h3{font-size:16px;font-family:var(--sans);font-weight:650}
p{margin:0 0 10px;max-width:72ch}
a{color:var(--t10)}
.contexte{color:var(--muted);margin-top:6px}
.entete{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;
  padding-bottom:18px;border-bottom:1px solid var(--rule)}
.choix{display:inline-flex;border:1px solid var(--rule);border-radius:8px;overflow:hidden;background:var(--surface)}
.choix button{border:0;background:transparent;color:var(--ink);font:inherit;padding:7px 14px;cursor:pointer}
.choix button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
button:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2.2fr);gap:32px;padding:26px 0 24px;align-items:end}
.chiffres{display:flex;gap:34px;flex-wrap:wrap}
.chiffre .valeur{font-family:var(--serif);font-size:44px;line-height:1;font-weight:600}
.chiffre .legende{color:var(--muted);font-size:13.5px;margin-top:6px}
.carte h2{font-size:17px;margin-bottom:12px}
.barre{display:flex;height:34px;border-radius:6px;overflow:hidden;background:var(--rule-soft)}
.barre span{display:block;height:100%;transition:width .35s ease}
.legende-carte{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}
.legende-carte div{border-top:3px solid var(--c);padding-top:6px;font-size:13.5px}
.legende-carte b{display:block;font-size:15px}
.legende-carte .neg{color:var(--muted)}
nav.onglets{display:flex;gap:4px;border-bottom:1px solid var(--rule);margin-top:6px;overflow-x:auto}
nav.onglets button{border:0;background:none;font:inherit;color:var(--muted);padding:10px 14px;cursor:pointer;
  border-bottom:3px solid transparent;margin-bottom:-1px;white-space:nowrap}
nav.onglets button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
section.panneau{display:none;padding-top:22px}
section.panneau.actif{display:block}
.grille{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:28px}
.bloc{background:var(--surface);border:1px solid var(--rule-soft);border-radius:10px;padding:18px 18px 14px}
.defile{overflow-x:auto}
.defile table{min-width:560px}
table{border-collapse:collapse;width:100%;font-size:14px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:12.5px;padding:6px 8px;border-bottom:1px solid var(--rule)}
td{padding:6px 8px;border-bottom:1px solid var(--rule-soft);vertical-align:top}
td.n,th.n{text-align:right;white-space:nowrap}
tr.cliquable{cursor:pointer}
tr.cliquable:hover td{background:var(--info-fond)}
.mini{display:block;height:6px;border-radius:3px;background:var(--t5);margin-top:4px}
.puce{display:inline-block;font-size:12.5px;padding:1px 8px;border-radius:999px;white-space:nowrap}
.puce.instruire{background:var(--alerte-fond);color:var(--alerte)}
.puce.examiner{background:var(--examen-fond);color:var(--examen)}
.puce.information{background:var(--info-fond);color:var(--muted)}
.note{color:var(--muted);font-size:13.5px}
.reglages{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px 24px;margin-bottom:18px}
label{display:block;font-size:13.5px;color:var(--muted);margin-bottom:4px}
select,input[type="number"]{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--rule);
  border-radius:6px;padding:6px 8px;width:100%}
input[type="range"]{width:100%;accent-color:var(--t10)}
.sortie{font-weight:600}
.resultats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:6px 0 16px}
.resultats div{border-left:3px solid var(--rule);padding:2px 0 2px 12px}
.resultats b{display:block;font-family:var(--serif);font-size:24px;font-weight:600}
.resultats span{color:var(--muted);font-size:13px}
.resultats .fort{border-left-color:var(--credit)}
.preselections{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.preselections button{font:inherit;font-size:13.5px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);
  border-radius:999px;padding:4px 12px;cursor:pointer}
svg text{fill:var(--muted);font:12px var(--sans)}
.pied{margin-top:36px;padding-top:14px;border-top:1px solid var(--rule);color:var(--muted);font-size:13px;max-width:none}
code{font-size:12.5px;word-break:break-all}
@media (max-width:820px){
  .hero,.grille{grid-template-columns:minmax(0,1fr)}
  .chiffre .valeur{font-size:36px}
  .legende-carte{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (prefers-reduced-motion:reduce){.barre span{transition:none}}
</style>
</head>
<body>
<div class="page">
  <header class="entete">
    <div>
      <h1>RiskLens</h1>
      <p class="contexte" id="contexte"></p>
    </div>
    <div>
      <label id="lib-confiance">Niveau de confiance</label>
      <div class="choix" role="group" aria-labelledby="lib-confiance">
        <button type="button" data-confiance="0.95" aria-pressed="false">95 %</button>
        <button type="button" data-confiance="0.99" aria-pressed="true">99 %</button>
      </div>
    </div>
  </header>

  <div class="hero">
    <div class="chiffres">
      <div class="chiffre"><div class="valeur" id="h-var"></div><div class="legende" id="h-var-lib"></div></div>
      <div class="chiffre"><div class="valeur" id="h-es"></div><div class="legende">Expected Shortfall à un jour</div></div>
    </div>
    <div class="carte">
      <h2>Où se loge le risque de queue</h2>
      <div class="barre" id="barre" role="img"></div>
      <div class="legende-carte" id="legende"></div>
    </div>
  </div>

  <nav class="onglets" role="tablist">
    <button role="tab" aria-selected="true" data-onglet="comite">Comité</button>
    <button role="tab" aria-selected="false" data-onglet="decision">Décision de vente</button>
    <button role="tab" aria-selected="false" data-onglet="stress">Stress</button>
    <button role="tab" aria-selected="false" data-onglet="controles">Contrôles</button>
    <button role="tab" aria-selected="false" data-onglet="methode">Méthode et sources</button>
  </nav>

  <section class="panneau actif" id="comite" role="tabpanel">
    <div class="grille">
      <div class="bloc">
        <h2>Premiers contributeurs à l'ES</h2>
        <p class="note">Contribution d'Euler : la somme sur les lignes égale l'ES. Cliquer une ligne pour simuler sa vente.</p>
        <div class="defile"><table id="t-contrib"></table></div>
      </div>
      <div class="bloc">
        <h2>La VaR tient-elle ?</h2>
        <p class="note" id="bt-resume"></p>
        <svg id="bt" viewBox="0 0 520 220" width="100%" role="img" aria-label="Pertes journalières et VaR prévue"></svg>
        <p class="note">Chaque VaR n'utilise que les 250 pertes précédentes. Pertes modélisées à positions constantes, pas les pertes réalisées par le fonds.</p>
      </div>
    </div>
  </section>

  <section class="panneau" id="decision" role="tabpanel">
    <div class="reglages">
      <div><label for="v-ligne">Ligne à vendre</label><select id="v-ligne"></select></div>
      <div><label for="v-montant">Montant vendu : <span class="sortie" id="v-montant-lib"></span></label>
        <input type="range" id="v-montant" min="0" step="1000000"></div>
    </div>
    <div class="resultats" id="v-resultats"></div>
    <p id="v-phrase"></p>
    <div class="bloc">
      <h2>Lignes où une vente réduit le plus le risque, par euro vendu</h2>
      <p class="note">ES par million détenu : contribution à l'ES divisée par la valeur de la ligne. Cliquer pour la sélectionner.</p>
      <div class="defile"><table id="t-intensite"></table></div>
    </div>
  </section>

  <section class="panneau" id="stress" role="tabpanel">
    <div class="preselections" id="presets"></div>
    <div class="reglages">
      <div><label for="s-taux">Choc parallèle de taux : <span class="sortie" id="s-taux-lib"></span></label>
        <input type="range" id="s-taux" min="-300" max="300" step="25" value="100"></div>
      <div><label for="s-spread">Choc de spread, hors Bund : <span class="sortie" id="s-spread-lib"></span></label>
        <input type="range" id="s-spread" min="-200" max="500" step="25" value="150"></div>
    </div>
    <div class="resultats" id="s-resultats"></div>
    <div class="bloc">
      <h2>Lignes les plus touchées</h2>
      <div class="defile"><table id="t-stress"></table></div>
    </div>
    <p class="note" style="margin-top:12px">Scénarios hypothétiques, sans probabilité attribuée. La revalorisation des flux mesure l'effet de convexité du modèle ; options et défaut sont hors modèle.</p>
  </section>

  <section class="panneau" id="controles" role="tabpanel">
    <div class="bloc">
      <h2>Lignes de l'inventaire à traiter</h2>
      <div class="defile"><table id="t-alertes"></table></div>
    </div>
    <div class="grille" style="margin-top:22px">
      <div class="bloc"><h2>Rapprochements</h2><table id="t-rappro"></table></div>
      <div class="bloc"><h2>Données manquantes</h2><table id="t-indispo"></table></div>
    </div>
  </section>

  <section class="panneau" id="methode" role="tabpanel">
    <div class="grille">
      <div>
        <h2>Ce que mesure l'outil</h2>
        <p>Les lignes de la section obligations à taux fixe en euros de l'inventaire publié sont modélisées par leurs flux théoriques : coupons annuels, remboursement à l'échéance, actualisation sur la courbe AAA de la BCE interpolée entre 2, 5 et 10 ans, plus un spread constant ajusté pour retrouver le prix publié.</p>
        <p>Les sensibilités aux nœuds de courbe et au spread sont appliquées aux 1 000 dernières variations quotidiennes observées. La VaR est la perte au rang arrondi supérieur de confiance x 1 000 ; l'ES est la moyenne des pires 1 000 x (1 - confiance) pertes, soit 10 journées à 99 %.</p>
        <p id="m-spread"></p>
        <h2 style="margin-top:18px">Ce qu'il ne mesure pas</h2>
        <p>Ce n'est ni la VaR du fonds ni un contrôle de ses limites : dérivés, autres sections de l'inventaire et passifs sont exclus. Options de remboursement anticipé, défaut et liquidité sont hors modèle. Les données sont historiques et ne correspondent pas à ce qui était disponible le 30/06/2025.</p>
      </div>
      <div class="bloc">
        <h2>Sources et empreintes</h2>
        <div id="sources"></div>
      </div>
    </div>
  </section>

  <p class="pied">Projet personnel sans lien avec Rothschild & Co. Aucune recommandation d'investissement. <span id="genere"></span></p>
</div>

<script id="donnees" type="application/json">__DONNEES__</script>
<script>
(function(){
"use strict";
var D = JSON.parse(document.getElementById("donnees").textContent);
var P = D.positions, S = D.scenarios, V = D.meta.valeur, N = S.d2.length;

/* ---------- moteur : mêmes formules que le moteur Python ---------- */
function montantsApresVente(isin, montant){
  return P.map(function(p){ return p.valeur - (p.isin === isin ? montant : 0); });
}
function sensibilites(m){
  var s = [0,0,0,0];
  for (var i=0;i<P.length;i++){ var w = m[i]/V, p = P[i];
    s[0]+=w*p.krd[0]; s[1]+=w*p.krd[1]; s[2]+=w*p.krd[2]; s[3]+=w*p.ds*p.beta; }
  return s;
}
function pertes(s){
  var L = new Array(N);
  for (var t=0;t<N;t++) L[t] = V*(s[0]*S.d2[t]+s[1]*S.d5[t]+s[2]*S.d10[t]+s[3]*S.ds[t]);
  return L;
}
function rang(a, n){ return Math.ceil(Number((a*n).toFixed(9))); }
function queue(L, a){
  var n = L.length, ordre = L.map(function(_,i){return i;});
  ordre.sort(function(x,y){ return L[y]-L[x] || x-y; });
  var masse = n*(1-a), poids = new Array(n).fill(0), reste = masse;
  for (var k=0;k<n;k++){ var pris = Math.min(1, Math.max(0, reste)); poids[ordre[k]] = pris/masse; reste -= pris; }
  var es = 0; for (var t=0;t<n;t++) es += L[t]*poids[t];
  return {var: L[ordre[n-rang(a,n)]], es: es, poids: poids};
}
function mesurer(m, a){
  var s = sensibilites(m), L = pertes(s), q = queue(L, a), T = [0,0,0,0];
  for (var t=0;t<N;t++){ var w=q.poids[t]; if(!w) continue;
    T[0]+=w*S.d2[t]; T[1]+=w*S.d5[t]; T[2]+=w*S.d10[t]; T[3]+=w*S.ds[t]; }
  var lignes = P.map(function(p,i){ return m[i]*(p.krd[0]*T[0]+p.krd[1]*T[1]+p.krd[2]*T[2]+p.ds*p.beta*T[3]); });
  return {var:q.var, es:q.es, pertes:L, lignes:lignes, facteurs:[V*s[0]*T[0],V*s[1]*T[1],V*s[2]*T[2],V*s[3]*T[3]]};
}
function stresser(m, taux, spread){
  var lin=0, tx=0, cr=0, reval=0, lignes=[];
  for (var i=0;i<P.length;i++){ var p=P[i], d=p.krd[0]+p.krd[1]+p.krd[2];
    var a = m[i]*d*taux/10000, b = m[i]*p.ds*spread/10000; lignes.push(a+b); tx+=a; cr+=b;
    var choc = (taux + (p.ds ? spread : 0))/10000, avant=0, apres=0;
    for (var f=0; f<p.flux.length; f++){ avant+=p.flux[f][1]; apres+=p.flux[f][1]*Math.exp(-choc*p.flux[f][0]); }
    reval += m[i]*(1-apres/avant); }
  return {lineaire:tx+cr, taux:tx, credit:cr, revalorisee:reval, lignes:lignes};
}
function backtester(m, a){
  var L = pertes(sensibilites(m)), debut = Math.max(250, N-250), sortie = [];
  for (var t=debut;t<N;t++) sortie.push({date:S.dates[t], perte:L[t], var:queue(L.slice(t-250,t), a).var});
  return sortie;
}
function kupiec(x, n, a){
  var p = 1-a, o = x/n;
  function lv(q){ return (x<n?(n-x)*Math.log(1-q):0) + (x>0?x*Math.log(q):0); }
  var lr = (o>0&&o<1) ? -2*(lv(p)-lv(o)) : -2*lv(p);
  return {lr:lr, p:erfc(Math.sqrt(lr/2))};
}
function erfc(x){ /* Numerical Recipes, précision 1.2e-7 */
  var z=Math.abs(x), t=1/(1+0.5*z);
  var r=t*Math.exp(-z*z-1.26551223+t*(1.00002368+t*(0.37409196+t*(0.09678418+t*(-0.18628806+t*(0.27886807+t*(-1.13520398+t*(1.48851587+t*(-0.82215223+t*0.17087277)))))))));
  return x>=0 ? r : 2-r;
}
window.RiskLens = {
  calculer: function(o){
    var m0 = P.map(function(p){return p.valeur;}), m1 = montantsApresVente(o.isin, o.montant);
    var a = mesurer(m0, o.confiance), b = mesurer(m1, o.confiance);
    var s0 = stresser(m0, o.taux, o.spread), s1 = stresser(m1, o.taux, o.spread);
    return {var_initial:a.var, es_initial:a.es, var_apres:b.var, es_apres:b.es, facteurs:a.facteurs,
            stress_initial:s0.lineaire, stress_apres:s1.lineaire, reval_initial:s0.revalorisee, reval_apres:s1.revalorisee};
  }
};

/* ---------- présentation ---------- */
var nf0 = new Intl.NumberFormat("fr-FR",{maximumFractionDigits:0});
var nf1 = new Intl.NumberFormat("fr-FR",{minimumFractionDigits:1,maximumFractionDigits:1});
var nf2 = new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2});
function eur(v){ return nf0.format(v)+" €"; }
function meur(v){ return nf1.format(v/1e6)+" M€"; }
function pct(v,d){ return (d===1?nf1:nf2).format(v*100)+" %"; }
function esc(t){ return String(t).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];}); }
function $(id){ return document.getElementById(id); }

var etat = {confiance:0.99, isin:D.meta.vente_isin, montant:D.meta.vente_montant, taux:100, spread:150};
var initial = P.map(function(p){return p.valeur;});
var NOMS = ["Taux 2 ans","Taux 5 ans","Taux 10 ans", D.meta.spread ? "Spread crédit" : "Spread (non raccordé)"];
var COULEURS = ["var(--t2)","var(--t5)","var(--t10)","var(--credit)"];

$("contexte").textContent = D.meta.fonds + ", inventaire publié au " + D.meta.date.split("-").reverse().join("/") +
  ". " + D.meta.lignes + " lignes à taux fixe en euros modélisées sur " + D.meta.inventaire +
  ", soit " + meur(V) + " et " + pct(V/D.meta.actif_net,1) + " de l'actif net.";
$("genere").textContent = "Généré le " + D.meta.genere + ".";
$("m-spread").textContent = D.meta.spread
  ? "Le facteur de spread est l'écart quotidien entre le rendement moyen des obligations d'entreprises allemandes et celui des titres fédéraux (Bundesbank). " +
    (D.meta.methode === "dts" ? "Chaque ligne y réagit en proportion de son propre spread (méthode Duration Times Spread)." : "Toutes les lignes y réagissent avec un bêta de 1.")
  : "La série de spread n'a pas encore été extraite : la VaR ne mesure que le risque de taux, le spread n'est mesuré qu'en stress.";

var courant = null;
function rendreComite(){
  courant = mesurer(initial, etat.confiance);
  $("h-var").textContent = meur(courant.var);
  $("h-var-lib").textContent = (D.meta.spread ? "VaR" : "VaR de taux") + " à un jour, " + pct(courant.var/V) + " de la valeur";
  $("h-es").textContent = meur(courant.es);
  var pos = courant.facteurs.map(function(v){return Math.max(v,0);}), tot = pos.reduce(function(a,b){return a+b;},0) || 1;
  $("barre").innerHTML = pos.map(function(v,k){ return '<span title="'+NOMS[k]+'" style="width:'+(v/tot*100)+'%;background:'+COULEURS[k]+'"></span>'; }).join("");
  $("barre").setAttribute("aria-label", NOMS.map(function(n,k){return n+" "+meur(courant.facteurs[k]);}).join(", "));
  $("legende").innerHTML = courant.facteurs.map(function(v,k){
    return '<div style="--c:'+COULEURS[k]+'"><b>'+meur(v)+'</b>'+NOMS[k]+' <span class="'+(v<0?'neg':'')+'">'+(v<0?'(compense)':pct(v/courant.es,1))+'</span></div>'; }).join("");
  var idx = P.map(function(_,i){return i;}).sort(function(a,b){return courant.lignes[b]-courant.lignes[a];}).slice(0,12);
  var max = courant.lignes[idx[0]];
  $("t-contrib").innerHTML = '<tr><th>Ligne</th><th class="n">Valeur</th><th class="n">Contribution</th><th class="n">Part</th><th class="n">ES par M€</th></tr>' +
    idx.map(function(i){ var c=courant.lignes[i];
      return '<tr class="cliquable" data-isin="'+P[i].isin+'"><td>'+esc(P[i].libelle)+'<span class="mini" style="width:'+(c/max*100)+'%"></span></td><td class="n">'+meur(P[i].valeur)+'</td><td class="n">'+eur(c)+'</td><td class="n">'+pct(c/courant.es,1)+'</td><td class="n">'+eur(c/P[i].valeur*1e6)+'</td></tr>'; }).join("");
  rendreBacktest();
}
function rendreBacktest(){
  var bt = backtester(initial, etat.confiance), x = bt.filter(function(b){return b.perte>b.var;}).length, k = kupiec(x, bt.length, etat.confiance);
  $("bt-resume").textContent = x + " dépassement" + (x>1?"s":"") + " sur " + bt.length + " jours, pour " + nf1.format(bt.length*(1-etat.confiance)) +
    " attendus. Test de Kupiec : p-value " + nf2.format(k.p) + (k.p<0.05 ? ", calibration rejetée." : ", calibration non rejetée.");
  var W=520,H=220,g=34,haut=Math.max.apply(null,bt.map(function(b){return Math.max(b.perte,b.var);})),bas=Math.min.apply(null,bt.map(function(b){return b.perte;}));
  var y=function(v){return 10+(haut-v)/(haut-bas)*(H-34);}, pas=(W-g)/bt.length, svg='';
  svg+='<line x1="'+g+'" x2="'+W+'" y1="'+y(0)+'" y2="'+y(0)+'" stroke="var(--rule)"/>';
  bt.forEach(function(b,i){ var xx=g+i*pas, ex=b.perte>b.var;
    svg+='<rect x="'+xx.toFixed(1)+'" width="'+Math.max(pas-0.6,0.8).toFixed(1)+'" y="'+Math.min(y(0),y(b.perte)).toFixed(1)+'" height="'+Math.abs(y(b.perte)-y(0)).toFixed(1)+'" fill="'+(ex?'var(--alerte)':'var(--t2)')+'"/>'; });
  svg+='<polyline fill="none" stroke="var(--ink)" stroke-width="1.6" points="'+bt.map(function(b,i){return (g+i*pas+pas/2).toFixed(1)+','+y(b.var).toFixed(1);}).join(' ')+'"/>';
  [haut,0].forEach(function(v){ svg+='<text x="0" y="'+(y(v)+4)+'">'+nf0.format(v/1e6)+' M</text>'; });
  svg+='<text x="'+g+'" y="'+(H-4)+'">'+bt[0].date.split("-").reverse().join("/")+'</text><text x="'+(W-70)+'" y="'+(H-4)+'">'+bt[bt.length-1].date.split("-").reverse().join("/")+'</text>';
  $("bt").innerHTML = svg;
}

function rendreDecision(){
  var i = P.findIndex(function(p){return p.isin===etat.isin;}), p = P[i];
  etat.montant = Math.min(etat.montant, p.valeur);
  var curseur = $("v-montant"); curseur.max = Math.floor(p.valeur/1e6)*1e6; curseur.value = etat.montant;
  $("v-montant-lib").textContent = meur(etat.montant);
  var base = mesurer(initial, etat.confiance), apres = mesurer(montantsApresVente(etat.isin, etat.montant), etat.confiance);
  var red = base.es - apres.es, parM = etat.montant ? red/etat.montant*1e6 : 0, prorata = base.es/V*1e6;
  $("v-resultats").innerHTML =
    '<div><b>'+meur(apres.es)+'</b><span>ES après vente, contre '+meur(base.es)+'</span></div>'+
    '<div><b>'+meur(apres.var)+'</b><span>VaR après vente, contre '+meur(base.var)+'</span></div>'+
    '<div class="fort"><b>'+eur(parM)+'</b><span>de réduction d\'ES par M€ vendu</span></div>'+
    '<div><b>'+eur(prorata)+'</b><span>par M€ pour une vente au prorata</span></div>';
  $("v-phrase").textContent = etat.montant ? ("Vendre " + meur(etat.montant) + " de " + p.libelle + " réduit l'ES " +
    nf2.format(parM/prorata) + " fois " + (parM>=prorata ? "plus" : "moins") + " qu'une vente au prorata de même montant.") : "Choisir un montant pour simuler la vente.";
  var intens = P.map(function(q,j){ return {j:j, v:base.lignes[j]/q.valeur*1e6}; }).sort(function(a,b){return b.v-a.v;}).slice(0,10);
  $("t-intensite").innerHTML = '<tr><th>Ligne</th><th>Échéance</th><th class="n">Valeur</th><th class="n">ES par M€ détenu</th></tr>' +
    intens.map(function(o){ var q=P[o.j];
      return '<tr class="cliquable" data-isin="'+q.isin+'"><td>'+esc(q.libelle)+'<span class="mini" style="width:'+(o.v/intens[0].v*100)+'%;background:var(--credit)"></span></td><td>'+q.echeance.split("-").reverse().join("/")+'</td><td class="n">'+meur(q.valeur)+'</td><td class="n">'+eur(o.v)+'</td></tr>'; }).join("");
}
function remplirLignes(){
  var base = mesurer(initial, 0.99);
  var ordre = P.map(function(p,i){return {i:i, v:base.lignes[i]/p.valeur};}).sort(function(a,b){return b.v-a.v;});
  $("v-ligne").innerHTML = ordre.map(function(o){ var p=P[o.i]; return '<option value="'+p.isin+'">'+esc(p.libelle)+' ('+meur(p.valeur)+')</option>'; }).join("");
  $("v-ligne").value = etat.isin;
}

function rendreStress(){
  $("s-taux-lib").textContent = (etat.taux>0?"+":"") + etat.taux + " pb";
  $("s-spread-lib").textContent = (etat.spread>0?"+":"") + etat.spread + " pb";
  var s = stresser(initial, etat.taux, etat.spread);
  $("s-resultats").innerHTML =
    '<div class="fort"><b>'+meur(s.lineaire)+'</b><span>perte linéaire, '+pct(s.lineaire/V)+' de la valeur</span></div>'+
    '<div><b>'+meur(s.taux)+'</b><span>dont taux</span></div>'+
    '<div><b>'+meur(s.credit)+'</b><span>dont crédit</span></div>'+
    '<div><b>'+meur(s.revalorisee)+'</b><span>en revalorisant les flux, soit '+meur(s.lineaire-s.revalorisee)+' d\'effet de convexité</span></div>';
  var idx = P.map(function(_,i){return i;}).sort(function(a,b){return s.lignes[b]-s.lignes[a];}).slice(0,10);
  $("t-stress").innerHTML = '<tr><th>Ligne</th><th class="n">Valeur</th><th class="n">Duration</th><th class="n">Perte linéaire</th><th class="n">En % de la ligne</th></tr>' +
    idx.map(function(i){ var p=P[i];
      return '<tr><td>'+esc(p.libelle)+'</td><td class="n">'+meur(p.valeur)+'</td><td class="n">'+nf2.format(p.krd[0]+p.krd[1]+p.krd[2])+'</td><td class="n">'+eur(s.lignes[i])+'</td><td class="n">'+pct(s.lignes[i]/p.valeur,1)+'</td></tr>'; }).join("");
}

function rendreControles(){
  var classe = {"À instruire":"instruire","À examiner":"examiner","Information":"information"};
  $("t-alertes").innerHTML = '<tr><th>Suite</th><th>Ligne</th><th>Contrôle</th><th>Constat</th><th>Action proposée</th></tr>' +
    D.alertes.map(function(a){ return '<tr><td><span class="puce '+classe[a.severite]+'">'+a.severite+'</span></td><td>'+esc(a.libelle)+'<br><span class="note">'+a.isin+'</span></td><td>'+esc(a.controle)+'</td><td>'+esc(a.constat)+'</td><td>'+esc(a.suite)+'</td></tr>'; }).join("");
  $("t-rappro").innerHTML = D.rapprochements.map(function(r){ return '<tr><td>'+esc(r.libelle)+'</td><td class="n">'+(r.ok?'Conforme':'Écart')+'</td></tr>'; }).join("");
  $("t-indispo").innerHTML = D.indisponibles.map(function(r){ return '<tr><td><b>'+esc(r.theme)+'</b><br><span class="note">'+esc(r.constat)+'</span></td></tr>'; }).join("");
  $("sources").innerHTML = D.sources.map(function(s){ return '<p><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.nom)+'</a><br><span class="note">'+(s.sha256?'SHA-256 <code>'+s.sha256+'</code>':'Non téléchargée dans cette version')+'</span></p>'; }).join("") +
    '<h3 style="margin-top:14px">Fichiers dérivés</h3>' + Object.keys(D.empreintes).map(function(k){ return '<p class="note">'+esc(k)+'<br><code>'+D.empreintes[k]+'</code></p>'; }).join("");
}
function remplirPresets(){
  $("presets").innerHTML = Object.keys(D.presets).map(function(k){ return '<button type="button" data-taux="'+D.presets[k][0]+'" data-spread="'+D.presets[k][1]+'">'+esc(k)+'</button>'; }).join("");
}

function tout(){ rendreComite(); rendreDecision(); rendreStress(); }
document.querySelectorAll("[data-confiance]").forEach(function(b){
  b.addEventListener("click", function(){ etat.confiance = Number(b.dataset.confiance);
    document.querySelectorAll("[data-confiance]").forEach(function(x){ x.setAttribute("aria-pressed", String(x===b)); }); tout(); });
});
document.querySelectorAll("nav.onglets button").forEach(function(b){
  b.addEventListener("click", function(){ ouvrir(b.dataset.onglet); });
});
function ouvrir(id){
  document.querySelectorAll("nav.onglets button").forEach(function(x){ x.setAttribute("aria-selected", String(x.dataset.onglet===id)); });
  document.querySelectorAll("section.panneau").forEach(function(s){ s.classList.toggle("actif", s.id===id); });
}
document.addEventListener("click", function(e){
  var tr = e.target.closest("tr[data-isin]"); if (!tr) return;
  etat.isin = tr.dataset.isin; $("v-ligne").value = etat.isin;
  var p = P.find(function(q){return q.isin===etat.isin;});
  etat.montant = Math.min(D.meta.vente_montant, Math.floor(p.valeur/1e6)*1e6);
  rendreDecision(); ouvrir("decision");
});
$("v-ligne").addEventListener("change", function(e){ etat.isin = e.target.value; rendreDecision(); });
$("v-montant").addEventListener("input", function(e){ etat.montant = Number(e.target.value); rendreDecision(); });
$("s-taux").addEventListener("input", function(e){ etat.taux = Number(e.target.value); rendreStress(); });
$("s-spread").addEventListener("input", function(e){ etat.spread = Number(e.target.value); rendreStress(); });
$("presets").addEventListener("click", function(e){ var b = e.target.closest("button"); if (!b) return;
  etat.taux = Number(b.dataset.taux); etat.spread = Number(b.dataset.spread); $("s-taux").value = etat.taux; $("s-spread").value = etat.spread; rendreStress(); });

remplirLignes(); remplirPresets(); rendreControles(); tout();
})();
</script>
</body>
</html>
"""
