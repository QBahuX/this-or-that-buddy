import discord
import asyncio
import random
from questions import QUESTIONS

class GameSession:
    def __init__(self, interaction, bot):
        self.interaction = interaction
        self.bot = bot
        self.channel = interaction.channel
        self.players = []
        self.answers = {}  # {user_id: [answers]}
        self.current_question = 0
        self.total_questions = 10
        
    async def start_game(self):
        """Start the complete game flow"""
        # Phase 1: Player registration
        if not await self.register_players():
            return
        
        # Phase 2: Play the game
        await self.play_game()
        
        # Phase 3: Calculate and show results
        await self.show_results()
    
    async def register_players(self):
        """Handle player registration phase"""
        embed = discord.Embed(
            title="🎮 This or That Compatibility Game",
            description="React with ✅ to join the game!\n\n**Rules:**\n• Minimum 2 players, maximum 5 players\n• You have 15 seconds to join\n• Answer 10 questions with 👍 or 👎\n• See your compatibility with other players!",
            color=0x00ff00
        )
        
        join_message = await self.interaction.followup.send(embed=embed)
        await join_message.add_reaction("✅")
        
        # Wait for reactions for 15 seconds
        def check(reaction, user):
            return (reaction.message.id == join_message.id and 
                   str(reaction.emoji) == "✅" and 
                   not user.bot)
        
        try:
            # Collect reactions for 15 seconds
            end_time = asyncio.get_event_loop().time() + 15.0
            while asyncio.get_event_loop().time() < end_time:
                remaining_time = end_time - asyncio.get_event_loop().time()
                if remaining_time <= 0:
                    break
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=remaining_time, check=check)
                    if user not in self.players and len(self.players) < 5:
                        self.players.append(user)
                        await self.interaction.followup.send(f"✅ {user.display_name} joined the game! ({len(self.players)}/5)")
                except asyncio.TimeoutError:
                    break
        
        except Exception as e:
            print(f"Error during registration: {e}")
        
        # Check if we have enough players
        if len(self.players) < 2:
            await self.interaction.followup.send("❌ Not enough players joined! You need at least 2 players to start the game.")
            return False
        
        # Initialize answers dictionary
        for player in self.players:
            self.answers[player.id] = []
        
        await self.interaction.followup.send(f"🎉 Game starting with {len(self.players)} players: {', '.join([p.display_name for p in self.players])}")
        await asyncio.sleep(2)
        return True
    
    async def play_game(self):
        """Play through all the questions"""
        selected_questions = random.sample(QUESTIONS, self.total_questions)
        
        for i, question in enumerate(selected_questions, 1):
            await self.ask_question(i, question)
            await asyncio.sleep(1)  # Brief pause between questions
    
    async def ask_question(self, question_num, question):
        """Ask a single question and collect responses"""
        embed = discord.Embed(
            title=f"Question {question_num}/{self.total_questions}",
            description=f"**{question}**\n\nReact with 👍 for the first option or 👎 for the second option!\nYou have 10 seconds to answer.",
            color=0x3498db
        )
        
        question_message = await self.interaction.followup.send(embed=embed)
        await question_message.add_reaction("👍")
        await question_message.add_reaction("👎")
        
        # Track who has answered
        answered_players = set()
        
        def check(reaction, user):
            return (reaction.message.id == question_message.id and 
                   str(reaction.emoji) in ["👍", "👎"] and 
                   user in self.players and
                   user.id not in answered_players)
        
        # Collect answers for 10 seconds
        end_time = asyncio.get_event_loop().time() + 10.0
        while asyncio.get_event_loop().time() < end_time and len(answered_players) < len(self.players):
            remaining_time = end_time - asyncio.get_event_loop().time()
            if remaining_time <= 0:
                break
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=remaining_time, check=check)
                if user.id not in answered_players:
                    self.answers[user.id].append(str(reaction.emoji))
                    answered_players.add(user.id)
            except asyncio.TimeoutError:
                break
        
        # Add "❓" for players who didn't answer in time
        for player in self.players:
            if player.id not in answered_players:
                self.answers[player.id].append("❓")
        
        # Show quick summary
        answered_count = len(answered_players)
        timeout_count = len(self.players) - answered_count
        summary_text = f"✅ {answered_count} answered"
        if timeout_count > 0:
            summary_text += f", ⏰ {timeout_count} timed out"
        
        await self.interaction.followup.send(summary_text)
    
    async def show_results(self):
        """Calculate and display compatibility results"""
        await self.interaction.followup.send("🧮 Calculating compatibility scores...")
        await asyncio.sleep(2)
        
        # Calculate compatibility between all pairs
        results = []
        
        for i in range(len(self.players)):
            for j in range(i + 1, len(self.players)):
                player1 = self.players[i]
                player2 = self.players[j]
                
                answers1 = self.answers[player1.id]
                answers2 = self.answers[player2.id]
                
                # Count matching answers (excluding timeouts)
                matches = 0
                valid_questions = 0
                
                for a1, a2 in zip(answers1, answers2):
                    if a1 != "❓" and a2 != "❓":
                        valid_questions += 1
                        if a1 == a2:
                            matches += 1
                
                # Calculate percentage
                if valid_questions > 0:
                    compatibility = round((matches / valid_questions) * 100)
                else:
                    compatibility = 0
                
                results.append((player1, player2, compatibility, matches, valid_questions))
        
        # Sort results by compatibility (highest first)
        results.sort(key=lambda x: x[2], reverse=True)
        
        # Create results embed
        embed = discord.Embed(
            title="💕 Compatibility Results",
            description="Here's how compatible each pair is based on their answers!",
            color=0xe91e63
        )
        
        # Add compatibility pairs
        for player1, player2, compatibility, matches, valid_questions in results:
            if compatibility >= 80:
                emoji = "💕"
            elif compatibility >= 60:
                emoji = "💖"
            elif compatibility >= 40:
                emoji = "💝"
            else:
                emoji = "💔"
            
            embed.add_field(
                name=f"{emoji} {player1.display_name} & {player2.display_name}",
                value=f"**{compatibility}% compatible**\n({matches}/{valid_questions} matching answers)",
                inline=True
            )
        
        await self.interaction.followup.send(embed=embed)
        
        # Show individual answer breakdown if requested
        breakdown_embed = discord.Embed(
            title="📊 Individual Answers Breakdown",
            description="Here's how each player answered:",
            color=0x9b59b6
        )
        
        for player in self.players:
            answers = self.answers[player.id]
            answer_summary = ""
            thumbs_up = answers.count("👍")
            thumbs_down = answers.count("👎")
            timeouts = answers.count("❓")
            
            answer_summary = f"👍 {thumbs_up} • 👎 {thumbs_down}"
            if timeouts > 0:
                answer_summary += f" • ❓ {timeouts}"
            
            breakdown_embed.add_field(
                name=player.display_name,
                value=answer_summary,
                inline=True
            )
        
        await self.interaction.followup.send(embed=breakdown_embed)
        
        # Thank you message
        await self.interaction.followup.send("🎉 Thanks for playing! Use `/start` to play again!")
