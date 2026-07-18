/**
 * Manasvi — Developer Experience Configuration
 * ==============================================
 * Everything the cinematic post-onboarding experience shows is driven
 * from this file. Edit values here — never hardcode message/lyric/
 * music content inside developer-experience.html itself.
 *
 * This plays the same role your brief described for
 * `config/developer_experience.ts` — kept as plain JS since the rest
 * of this project is vanilla JS/HTML rather than a TypeScript build.
 */

window.DEV_EXPERIENCE_CONFIG = {

  // ---------------------------------------------------------------
  // Eligible users
  // ---------------------------------------------------------------
  // Only accounts whose email appears here ever see this experience.
  // Everyone else goes straight from onboarding to the dashboard.
  // Add / remove emails freely — nothing else needs to change.
  eligibleEmails: [
    "manav.rahulrastogi@gmail.com",
  ],

  // Fallback for when you don't know someone's email yet: match on
  // their first name or full name instead (case-insensitive). Once
  // you learn their real email, move it into eligibleEmails above and
  // you can remove the name here if you want tighter matching.
  eligibleNames: [
    "Manasvi",
    "Manasvi Garg",
    "ethan",
  ],


  // ---------------------------------------------------------------
  // Theme
  // ---------------------------------------------------------------
  theme: {
    bgFrom: "#0b0c10",
    bgVia: "#12141b",
    bgTo: "#0b0c10",
    glow1: "rgba(167,139,250,0.16)",  // violet
    glow2: "rgba(94,234,207,0.12)",   // teal
    accent: "#a78bfa",
    textPrimary: "#f2f0ea",
    textMuted: "#8a8f98",
  },

  // ---------------------------------------------------------------
  // Pages
  // ---------------------------------------------------------------
  // All three pages share the exact same layout: a small title, a
  // stack of large lyric cards, and a nav button. Every string in
  // `cards` becomes its own card - so break paragraphs into individual
  // sentences rather than writing one long block of text.
  pages: [

    {


      title: "<strong>HAPPY BIRTHDAY MANU 🌺</strong>, and this 21st birthday developer wants to convey!!",

      music: "music/page1.mp3",

      cards: [

        "Haan woh jo tera aaina,Teri baliyan,Tera kangana,Teri galiyan Nadaniyan Sun jaaniya Badi acchi lagti hain",

        "Woh tera roothna Fasana tera rooth kar maan jaana Sanwar kar muskurana Bada accha lagta hai",

        "Main aakar tujhe thaam lun mere rab ki tarah Yaad karun aayat ki tarah Tujhe saam lun mazhab ki tarah Meri barkaton mein rehmat ki tarah"

      ],

      buttonText: "Next →"


    },

    {

      title: "A Little Something,<strong> YOUR FAVOURITE</strong>",

      music: "music/page2.mp3",

      cards: [

        "Tere iss ghar ko sajaane ke liye Hai yahi ek dhun",

        "Sanam ko apna banaane ke liye Hai yahi ek dhun Hai yahi ek dhun",

        "Ho-oh-oh-oh-oh Ho-oh-oh-oh Ey-Ey-Ey-Eyy.Ek dhun Ho-oh-oh-oh-oh Ho-oh-oh-oh Ey-Ey-Ey-Eyy.Ek dhun"

      ],
        buttonText: "Next →"
    },
    {

      title: "From The Developer",

      music: "music/page3.mp3",

      cards: [

        "Tu Hi Chain Dil Da Mere Kyun Labhdiyan Ne Nazar Vi Tere Dil Da Pata?",

        "Saah Vi Karti Naam Main Tere Bas Tenu Hi Na Khabar Ve Tu Hi Mera Jahaan",

        "Mera Jahaan! Mera Jahaan! Mera Jahaan! Mera Jahaan!"

      ],
       buttonText: "Next →"

    },

    {

      title: "One Last Thing, <strong>COMEBACK!!!</strong>",

      music: "music/page4.mp3",

      cards: [

        "Chanda chaandani bikhere Tu hai naheen paas mere Ab to aa jaao mere sonhiya",

        "Sooni tere bin yih raaten Sooni sooni saari baaten Yoon nah hamen tarpa ve sonhiya",

        "Tere bin Naaheen laage jiya Tere bin Ab to aaja piya Tere bin"

      ],
       buttonText: "Continue to Manasvi →"

    }

  ]
};
