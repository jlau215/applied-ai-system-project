# Model Card — PawPal+ AI Assistant

AI isn't just about what works — it's about what's responsible. This document reflects on the limitations, risks, and collaboration process behind the RAG-based AI Assistant added to PawPal+.

---

## Limitations and Biases

*What are the limitations or biases in your system?*
- Some limitations/bias in my system are that there is some reliance on the local knowledge base, web mode can have bias with the search engine, and model bias since LLama 3.3's data is mainly aimed towards English. Other limitations is that the feedback feature is only for logging and the retrieval system matches stemmed words which is a cheap and local approach.

---

## Potential for Misuse

*Could your AI be misused, and how would you prevent that?*
- The AI could be misused if users decide to see its responses as always true. The problem is that if users use web mode, there is bound to be some bias, which can cause misinformation or confusion. This could happen especially if a user asks for medical or food advice as a substitute for a veterinarian. I could prevent this by having the system remind users to always confirm advice with a vet. I could also have the AI model focus on only pet care related topics to avoid weak responses.

---

## Surprises in Reliability Testing

*What surprised you while testing your AI's reliability?*
- At first, I tried implementing Google's Gemini API, but it ended up being unreliable due to the free plan's limitations. This caused the AI to be unable to give a response. After switching to Groq and adding a knowledge base as a backup, the AI became more reliable. Since Groq's free plan also has some limitations with queries, there is a local mode.

---

## AI Collaboration Reflection

*Describe your collaboration with AI during this project. Identify one instance when the AI gave a helpful suggestion and one instance where its suggestion was flawed or incorrect.*
- My collaboration with AI during this project was helpful and informative. While working on this project, the AI gave suggestions for my plan to make sure it covers what I need done. One instance when the AI gave a helpful suggestion was when Gemini's API wasn't working. It suggested a few free alternatives which is how I ended up using Groq. One instance where the AI's suggestion was incorrect was when Gemini's API stopped working and suggested to create a local knowledge base and use it exclusively only. This went against what I planned since I wanted the implementation to be able to use a search engine to find accurate answers online, instead of limited answers.