Attribute VB_Name = "RiskLens"
Option Explicit

' RiskLens : verification independante et exports pour le classeur du comite.
'
' La verification ne relit aucune perte calculee par les formules du classeur :
' elle repart des poids apres vente, des sensibilites aux trois noeuds de taux et
' au facteur de spread, et des variations observees ; elle recalcule les 1000
' pertes, les trie et en deduit VaR et ES.
' Elle compare ensuite ses resultats a ceux du classeur.
'
' Le module n'utilise que des plages nommees (RL_...) : il ne depend ni des noms
' d'onglets ni de la position des cellules. Le code source est en ASCII ; les
' accents des messages sont produits par la fonction Texte.

Private Const TOLERANCE_EUR As Double = 0.01

Private Function Plage(ByVal nom As String) As Range
    Set Plage = ThisWorkbook.Names(nom).RefersToRange
End Function

' Remplace {e} par e accent aigu, {E} par E accent aigu, {a} par a accent grave, {o} par o circonflexe.
Private Function Texte(ByVal s As String) As String
    s = Replace(s, "{e}", ChrW(233))
    s = Replace(s, "{E}", ChrW(201))
    s = Replace(s, "{a}", ChrW(224))
    s = Replace(s, "{o}", ChrW(244))
    Texte = s
End Function

Public Sub VerifierRiskLens()
    On Error GoTo Echec
    Verifier
    MsgBox Texte("V{e}rification r{e}ussie : VaR et ES recalcul{e}es ind{e}pendamment concordent avec le classeur."), _
        vbInformation, "RiskLens"
    Exit Sub
Echec:
    Plage("RL_Statut_VBA").Value = Texte("{E}CHEC")
    MsgBox Texte("V{e}rification interrompue : ") & Err.Description, vbExclamation, "RiskLens"
End Sub

Private Sub Verifier()
    Dim poids As Variant, sens As Variant, sensSpread As Variant, chocs As Variant
    Dim s(1 To 4) As Double, pertes() As Double
    Dim n As Long, m As Long, i As Long, k As Long, t As Long
    Dim valeur As Double, confiance As Double, somme As Double
    Dim varVBA As Double, esVBA As Double

    Application.CalculateFull
    If CStr(Plage("RL_Valide").Value) <> "OK" Then _
        Err.Raise vbObjectError + 1, , Texte("param{e}tres invalides, voir l'onglet Param{e}tres.")

    poids = Plage("RL_Poids_Apres").Value2
    sens = Plage("RL_Sensibilites").Value2
    sensSpread = Plage("RL_Sensibilite_Spread").Value2
    chocs = Plage("RL_Variations").Value2
    valeur = Nombre(Plage("RL_NAV").Value2, "valeur du portefeuille")
    confiance = Nombre(Plage("RL_Confiance").Value2, "niveau de confiance")
    n = UBound(poids, 1)
    m = UBound(chocs, 1)

    ' Sensibilites du portefeuille : somme des poids x sensibilites de chaque ligne.
    For i = 1 To n
        somme = somme + Nombre(poids(i, 1), "poids ligne " & i)
        For k = 1 To 3
            s(k) = s(k) + poids(i, 1) * Nombre(sens(i, k), "sensibilit" & ChrW(233) & " ligne " & i)
        Next k
        s(4) = s(4) + poids(i, 1) * Nombre(sensSpread(i, 1), "sensibilit" & ChrW(233) & " spread ligne " & i)
    Next i
    If Abs(somme - 1#) > 0.000000001 Then Err.Raise vbObjectError + 2, , "la somme des poids ne vaut pas 100 %."

    ' Pertes historiques : valeur x somme des sensibilites x variations (3 taux et le spread).
    ReDim pertes(1 To m)
    For t = 1 To m
        For k = 1 To 4
            pertes(t) = pertes(t) + valeur * s(k) * Nombre(chocs(t, k), "variation, ligne " & t)
        Next k
    Next t
    TriRapide pertes, 1, m
    varVBA = pertes(RangVaR(confiance, m))
    esVBA = MoyenneQueue(pertes, confiance)

    Comparer varVBA, Plage("RL_VaR_Apres").Value2, "VaR"
    Comparer esVBA, Plage("RL_ES_Apres").Value2, "ES"
    If Abs(Nombre(Plage("RL_Ecart_Contributions").Value2, "rapprochement des contributions")) > TOLERANCE_EUR Then _
        Err.Raise vbObjectError + 3, , Texte("les contributions ne se rapprochent pas de l'ES.")

    Plage("RL_Horodatage").Value = Now
    Plage("RL_Horodatage").NumberFormat = "dd/mm/yyyy hh:mm"
    Plage("RL_Statut_VBA").Value = "OK"
End Sub

Private Function Nombre(ByVal v As Variant, ByVal quoi As String) As Double
    If IsError(v) Or IsEmpty(v) Or VarType(v) = vbString Then _
        Err.Raise vbObjectError + 10, , Texte("valeur non num{e}rique : ") & quoi
    Nombre = CDbl(v)
End Function

Private Sub Comparer(ByVal calcule As Double, ByVal classeur As Variant, ByVal nom As String)
    If Abs(calcule - Nombre(classeur, nom)) > TOLERANCE_EUR Then _
        Err.Raise vbObjectError + 4, , Texte("{e}cart sur ") & nom & " : VBA " & Format(calcule, "#,##0.00") & _
            ", classeur " & Format(classeur, "#,##0.00")
End Sub

' Rang croissant de la VaR : arrondi superieur de confiance x nombre de scenarios.
Private Function RangVaR(ByVal confiance As Double, ByVal m As Long) As Long
    RangVaR = Application.WorksheetFunction.RoundUp(Round(confiance * m, 9), 0)
End Function

' Moyenne des m x (1 - confiance) pires pertes ; la derniere peut compter en partie.
Private Function MoyenneQueue(ByRef tri() As Double, ByVal confiance As Double) As Double
    Dim masse As Double, reste As Double, part As Double, total As Double, i As Long
    masse = UBound(tri) * (1# - confiance)
    reste = masse
    For i = UBound(tri) To LBound(tri) Step -1
        If reste <= 0# Then Exit For
        part = reste
        If part > 1# Then part = 1#
        total = total + part * tri(i)
        reste = reste - part
    Next i
    MoyenneQueue = total / masse
End Function

Private Sub TriRapide(ByRef a() As Double, ByVal premier As Long, ByVal dernier As Long)
    Dim i As Long, j As Long, pivot As Double, tmp As Double
    i = premier: j = dernier: pivot = a((premier + dernier) \ 2)
    Do While i <= j
        Do While a(i) < pivot: i = i + 1: Loop
        Do While a(j) > pivot: j = j - 1: Loop
        If i <= j Then
            tmp = a(i): a(i) = a(j): a(j) = tmp
            i = i + 1: j = j - 1
        End If
    Loop
    If premier < j Then TriRapide a, premier, j
    If i < dernier Then TriRapide a, i, dernier
End Sub

Private Function CheminSortie(ByVal prefixe As String, ByVal extension As String) As String
    If Len(ThisWorkbook.Path) = 0 Then Err.Raise vbObjectError + 20, , "enregistrez d'abord le classeur."
    CheminSortie = ThisWorkbook.Path & Application.PathSeparator & prefixe & "-" & _
        Format(Now, "yyyymmdd-hhnnss") & "." & extension
    If Len(Dir(CheminSortie)) > 0 Then Err.Raise vbObjectError + 21, , Texte("un fichier porte d{e}j{a} ce nom, r{e}essayez.")
End Function

Public Sub ExporterNoteComite()
    Dim cible As String
    On Error GoTo Echec
    Verifier
    cible = CheminSortie("RiskLens-Comite", "pdf")
    Plage("RL_Zone_Comite").Worksheet.ExportAsFixedFormat Type:=xlTypePDF, Filename:=cible, _
        Quality:=xlQualityStandard, IncludeDocProperties:=True, IgnorePrintAreas:=False, OpenAfterPublish:=False
    MsgBox Texte("Note export{e}e : ") & cible, vbInformation, "RiskLens"
    Exit Sub
Echec:
    MsgBox Texte("Export interrompu : ") & Err.Description, vbExclamation, "RiskLens"
End Sub

Public Sub ExporterResultatsCSV()
    Dim cible As String, donnees As Variant, contenu As String, ligne As String
    Dim r As Long, c As Long
    On Error GoTo Echec
    Verifier
    cible = CheminSortie("RiskLens-Positions", "csv")
    donnees = Plage("RL_Tableau_Positions").Value2
    For r = 1 To UBound(donnees, 1)
        ligne = ""
        For c = 1 To UBound(donnees, 2)
            If c > 1 Then ligne = ligne & ";"
            ligne = ligne & Champ(donnees(r, c))
        Next c
        contenu = contenu & ligne & vbCrLf
    Next r
    EcrireTexte cible, contenu
    MsgBox Texte("R{e}sultats export{e}s : ") & cible, vbInformation, "RiskLens"
    Exit Sub
Echec:
    MsgBox Texte("Export interrompu : ") & Err.Description, vbExclamation, "RiskLens"
End Sub

Private Function Champ(ByVal v As Variant) As String
    If IsError(v) Then Err.Raise vbObjectError + 30, , "cellule en erreur dans le tableau des positions."
    Champ = Chr(34) & Replace(CStr(v), Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function

' UTF-8 sous Windows. Sous Mac, ecriture native, accents remplaces pour rester lisible partout.
Private Sub EcrireTexte(ByVal chemin As String, ByVal contenu As String)
#If Mac Then
    Dim f As Integer
    f = FreeFile
    Open chemin For Output As #f
    Print #f, SansAccents(contenu);
    Close #f
#Else
    Dim flux As Object
    Set flux = CreateObject("ADODB.Stream")
    flux.Type = 2
    flux.Charset = "utf-8"
    flux.Open
    flux.WriteText contenu
    flux.SaveToFile chemin, 2
    flux.Close
#End If
End Sub

Private Function SansAccents(ByVal s As String) As String
    Dim avec As Variant, sans As Variant, i As Long
    avec = Array(233, 232, 234, 224, 226, 244, 238, 239, 251, 249, 231, 201, 200, 202, 192, 194, 212, 199, 339)
    sans = Array("e", "e", "e", "a", "a", "o", "i", "i", "u", "u", "c", "E", "E", "E", "A", "A", "O", "C", "oe")
    For i = LBound(avec) To UBound(avec)
        s = Replace(s, ChrW(avec(i)), sans(i))
    Next i
    SansAccents = s
End Function

Public Sub InstallerCommandes()
    Dim feuille As Worksheet, bouton As Shape, macros As Variant, libelles As Variant
    Dim i As Long, haut As Double
    Set feuille = Plage("RL_Valide").Worksheet
    haut = Plage("RL_Valide").Offset(4, 0).Top
    macros = Array("VerifierRiskLens", "ExporterNoteComite", "ExporterResultatsCSV")
    libelles = Array(Texte("V{e}rifier ind{e}pendamment"), Texte("Exporter la note (PDF)"), Texte("Exporter les positions (CSV)"))
    For i = 0 To 2
        On Error Resume Next
        feuille.Shapes("RiskLens_" & i).Delete
        On Error GoTo 0
        Set bouton = feuille.Shapes.AddShape(5, feuille.Range("B1").Left + i * 200, haut, 190, 28)
        bouton.Name = "RiskLens_" & i
        bouton.TextFrame.Characters.Text = libelles(i)
        bouton.TextFrame.Characters.Font.Size = 10
        bouton.TextFrame.Characters.Font.Color = RGB(255, 255, 255)
        bouton.Fill.ForeColor.RGB = RGB(25, 51, 74)
        bouton.OnAction = "'" & Replace(ThisWorkbook.Name, "'", "''") & "'!" & macros(i)
    Next i
    MsgBox Texte("Trois commandes ajout{e}es {a} l'onglet Param{e}tres. Enregistrez le classeur au format .xlsm."), _
        vbInformation, "RiskLens"
End Sub
