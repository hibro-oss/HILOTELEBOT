1: installer opencode
https://opencode.ai/ c'est une alternative à Claude code, ça tourne en local mais Claude Code appelle les API Anthropic pour utiliser le modèle d'IA et donc il faut avoir un model IA en plus mais déjà installer on commence par installer ça.
Pour windows: https://opencode.ai/docs/windows-wsl

2: tester un modèle d'IA locale
Comme tu as une carte graphique pas dégueulasse tu peux essayer d'avoir une IA sur ton PC directement,
il faut des models "open", que tu peux télécharger sans payer.
Aller sur https://ollama.com/search, tu cherches des modèles avec des tags genre '4b' '8b', parce que ça veut dire téléchargeables, 'cloud' ça veut dire utiliser l'api donc payants. Les meilleurs en ce moment sont Qwen, Minmax, Llama ou Deepseek.
Tu vérifies ce que ta carte peut gérer (plus le nombre devant le 'b' est grand meilleur le modèle mais plus il y a des chances que ta carte graphique soit pas assez puissante).
Tu ajoutes ton IA locale dans opencode: https://opencode.ai/docs/providers/#llamacpp
Ensuite dans opencode tu fais /models pour le choisir.
Aussi même si ça fonctionne y a moyen que les réponses soient très lentes.

3: créer un compte openrouter
Si l'IA locale n'est pas suffisant tu peux utiliser une API avec des modèles gratuits https://openrouter.ai/.
Tu créés un compte. Ensuite tu créés une clé API et tu lances pencode et tu configures openrouter avec /connect, tu copie-colle ta clé API.
Après /models et tu choisis un modèle marqué 'free'.
Attention même pour utiliser les API gratuites il faut mettre une petite somme sur le compte openrouter, ça va pas descendre masi il faut les mettre (5€ ça suffit).
Le problème des modèles gratuits c'est que tu peux être limité, donc si ça bloque sur un modèle tu pars sur un autre.
