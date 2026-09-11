"""
MORPHEUS CHAT - Session-Memory Integration Module
Seamless integration of persistent memory with existing session management,
enabling cross-session continuity and context reconstruction.

Integration Strategy:
- Memory manager as singleton service initialized at startup
- Session-scoped memory context injection
- Automatic memory storage during conversations
- Context window enhancement with relevant memories
- Privacy-preserving cross-session state management
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID

from memory.memory_core import (
    MemoryManager, MemoryConfiguration, MemoryType, MemoryImportance, MemoryScope
)
from schemas.session import PromptEventMemoryObject, PromptEventType, PromptMemoryTags
from schemas.session import SessionMetadata, SessionCreationRequest, SessionID, UserID

logger = logging.getLogger(__name__)


class SessionMemoryContext:
    """
    Session-scoped memory context for managing conversation continuity.
    
    Handles automatic memory storage, context reconstruction, and relevance scoring
    within the lifecycle of a single session.
    """
    
    def __init__(
        self, 
        session_id: SessionID, 
        user_id: UserID, 
        memory_manager: MemoryManager,
        max_context_memories: int = 10
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.memory_manager = memory_manager
        self.max_context_memories = max_context_memories
        
        # Session-specific memory tracking
        self.session_memories: List[UUID] = []
        self.context_memories: List[Dict[str, Any]] = []
        self.conversation_buffer: List[Dict[str, str]] = []
        
        # Context window management
        self.context_tokens_used = 0
        self.max_context_tokens = 8192  # Will be updated from session config
        
        logger.info(f"Memory context initialized for session {session_id}")
    
    async def initialize_context(self, custom_instructions: Optional[str] = None) -> str:
        """
        Initialize session context with relevant memories and instructions.
        
        Returns enhanced system prompt with memory context.
        """
        try:
            # Retrieve relevant memories for this user
            memory_types = [
                MemoryType.CORE_FACT,
                MemoryType.CUSTOM_INSTRUCTION,
                MemoryType.CONVERSATION
            ]
            
            memories = await self.memory_manager.retrieve_memories(
                user_id=self.user_id,
                memory_types=memory_types,
                importance_threshold=MemoryImportance.MEDIUM,
                limit=self.max_context_memories
            )
            
            self.context_memories = memories
            
            # Build enhanced system prompt
            context_prompt = await self._build_context_prompt(custom_instructions)
            
            logger.info(f"Initialized context with {len(memories)} memories for session {self.session_id}")
            return context_prompt
            
        except Exception as e:
            logger.error(f"Failed to initialize memory context: {e}")
            return custom_instructions or ""
    
    async def _build_context_prompt(self, custom_instructions: Optional[str] = None) -> str:
        """Build enhanced system prompt with memory context"""
        prompt_parts = []
        
        # Add custom instructions
        if custom_instructions:
            prompt_parts.append(f"User Instructions: {custom_instructions}")
        
        # Add core facts about the user
        core_facts = [m for m in self.context_memories if m['memory_type'] == MemoryType.CORE_FACT.value]
        if core_facts:
            facts_text = "\n".join([f"- {m['content']}" for m in core_facts[:5]])
            prompt_parts.append(f"Key Facts About User:\n{facts_text}")
        
        # Add relevant conversation history
        recent_conversations = [
            m for m in self.context_memories 
            if m['memory_type'] == MemoryType.CONVERSATION.value
        ][:3]
        
        if recent_conversations:
            conv_text = "\n".join([
                f"Previous context: {m['content'][:200]}..." 
                for m in recent_conversations
            ])
            prompt_parts.append(f"Recent Context:\n{conv_text}")
        
        # Add memory context instructions
        if self.context_memories:
            prompt_parts.append(
                "Use the above context to provide personalized, continuous assistance. "
                "Reference previous conversations when relevant, but don't explicitly mention "
                "that you're accessing stored memories unless asked."
            )
        
        return "\n\n".join(prompt_parts)
    
    async def store_conversation_turn(
        self, 
        user_message: str, 
        assistant_response: str,
        turn_metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Store a conversation turn in memory with appropriate importance scoring.
        
        Returns memory_id for the stored conversation.
        """
        try:
            # Create conversation content
            conversation_content = f"User: {user_message}\nAssistant: {assistant_response}"
            
            # Determine importance based on content characteristics
            importance = await self._assess_conversation_importance(
                user_message, assistant_response, turn_metadata
            )
            
            # Store in memory
            memory_id = await self.memory_manager.store_memory(
                user_id=self.user_id,
                content=conversation_content,
                memory_type=MemoryType.CONVERSATION,
                importance=importance,
                scope=MemoryScope.PRIVATE,
                source_session=self.session_id,
                tags=await self._extract_conversation_tags(user_message, assistant_response),
                metadata={
                    'turn_index': len(self.conversation_buffer),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    **(turn_metadata or {})
                }
            )
            
            self.session_memories.append(memory_id)
            self.conversation_buffer.append({
                'user': user_message,
                'assistant': assistant_response,
                'memory_id': str(memory_id)
            })
            
            logger.debug(f"Stored conversation turn {memory_id} for session {self.session_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store conversation turn: {e}")
            raise
    
    async def _assess_conversation_importance(
        self, 
        user_message: str, 
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryImportance:
        """
        Assess conversation importance using heuristics and content analysis.
        
        This could be enhanced with ML-based importance scoring.
        """
        # High importance indicators
        high_importance_indicators = [
            'remember', 'important', 'prefer', 'don\'t like', 'always', 'never',
            'my name is', 'call me', 'i am', 'i work', 'i live', 'my job'
        ]
        
        # Medium importance indicators
        medium_importance_indicators = [
            'question', 'help', 'explain', 'how to', 'what is', 'why',
            'project', 'work on', 'learning', 'studying'
        ]
        
        combined_text = (user_message + " " + assistant_response).lower()
        
        # Check for personal information or preferences
        if any(indicator in combined_text for indicator in high_importance_indicators):
            return MemoryImportance.HIGH
        
        # Check for substantive content
        if (len(combined_text) > 200 and 
            any(indicator in combined_text for indicator in medium_importance_indicators)):
            return MemoryImportance.MEDIUM
        
        # Tool usage or code generation
        if metadata and metadata.get('tools_used'):
            return MemoryImportance.MEDIUM
        
        # Default to low importance for casual conversation
        return MemoryImportance.LOW
    
    async def _extract_conversation_tags(
        self, 
        user_message: str, 
        assistant_response: str
    ) -> List[str]:
        """Extract relevant tags from conversation content"""
        tags = []
        
        # Topic-based tags
        topic_keywords = {
            'coding': ['code', 'program', 'function', 'bug', 'debug', 'python', 'javascript'],
            'math': ['calculate', 'equation', 'formula', 'solve', 'mathematics'],
            'writing': ['write', 'essay', 'document', 'story', 'article'],
            'research': ['research', 'analyze', 'study', 'investigate', 'explore'],
            'personal': ['myself', 'personal', 'preference', 'like', 'dislike']
        }
        
        combined_text = (user_message + " " + assistant_response).lower()
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                tags.append(topic)
        
        # Length-based tags
        if len(combined_text) > 500:
            tags.append('detailed')
        
        return tags
    
    async def store_extracted_fact(
        self, 
        fact: str, 
        importance: MemoryImportance = MemoryImportance.HIGH
    ) -> UUID:
        """
        Store an extracted user fact (name, preference, etc.) as a core fact.
        
        These are given high importance and long retention.
        """
        memory_id = await self.memory_manager.store_memory(
            user_id=self.user_id,
            content=fact,
            memory_type=MemoryType.CORE_FACT,
            importance=importance,
            scope=MemoryScope.PRIVATE,
            source_session=self.session_id,
            tags=['user_fact', 'extracted'],
            metadata={
                'extracted_at': datetime.now(timezone.utc).isoformat(),
                'extraction_session': str(self.session_id)
            }
        )
        
        logger.info(f"Stored extracted fact: {fact[:50]}...")
        return memory_id
    
    async def store_document_memory(
        self, 
        document_content: str, 
        filename: str,
        document_type: str = "upload"
    ) -> UUID:
        """Store uploaded document content with appropriate metadata"""
        memory_id = await self.memory_manager.store_memory(
            user_id=self.user_id,
            content=document_content,
            memory_type=MemoryType.DOCUMENT,
            importance=MemoryImportance.MEDIUM,
            scope=MemoryScope.PRIVATE,
            source_session=self.session_id,
            tags=['document', document_type, filename.split('.')[-1].lower()],
            metadata={
                'filename': filename,
                'document_type': document_type,
                'file_size': len(document_content),
                'uploaded_at': datetime.now(timezone.utc).isoformat()
            }
        )
        
        logger.info(f"Stored document memory for {filename}")
        return memory_id
    
    async def store_prompt_event_memory(
        self,
        prompt_event: PromptEventMemoryObject
    ) -> UUID:
        """Store prompt event as first-class memory object with immediate semantic indexing"""
        try:
            # Generate content for semantic embedding
            embedding_content = f"""Prompt Event: {prompt_event.event_type.value}
User Input: {prompt_event.user_input or 'N/A'}
Generated Prompt: {prompt_event.prompt_content}
Response: {prompt_event.response_content or 'N/A'}
Context Tags: {', '.join(prompt_event.memory_tags.semantic_tags)}
Technical Context: {', '.join(prompt_event.memory_tags.technical_context)}
Collaboration Context: {', '.join(prompt_event.memory_tags.collaboration_context)}"""
            
            # Determine importance based on event quality
            if prompt_event.is_high_quality:
                importance = MemoryImportance.HIGH
            elif prompt_event.memory_priority == "medium":
                importance = MemoryImportance.MEDIUM
            else:
                importance = MemoryImportance.LOW
            
            # Store in memory system with immediate semantic indexing
            memory_id = await self.memory_manager.store_memory(
                user_id=self.user_id,
                content=embedding_content,
                memory_type=MemoryType.SYSTEM_EVENT,  # Prompt events are system events
                importance=importance,
                scope=MemoryScope.PRIVATE,
                source_session=self.session_id,
                tags=self._generate_prompt_event_tags(prompt_event),
                metadata={
                    'prompt_event_id': str(prompt_event.event_id),
                    'event_type': prompt_event.event_type.value,
                    'generation_time_ms': prompt_event.generation_time_ms,
                    'prompt_length': prompt_event.prompt_length,
                    'quality_score': prompt_event.memory_tags.quality_score,
                    'relevance_score': prompt_event.memory_tags.relevance_score,
                    'adaptations_applied': prompt_event.adaptations_applied,
                    'user_feedback_score': prompt_event.user_feedback_score,
                    'semantic_similarity_scores': prompt_event.semantic_similarity_scores,
                    'created_at': prompt_event.created_at.isoformat(),
                    'is_high_quality': prompt_event.is_high_quality,
                    'memory_priority': prompt_event.memory_priority
                }
            )
            
            # Update the prompt event with consolidation info
            prompt_event.mark_consolidated(str(memory_id))
            
            logger.info(f"Stored prompt event {prompt_event.event_id} as memory {memory_id} with immediate semantic indexing")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store prompt event memory: {e}")
            raise
    
    def _generate_prompt_event_tags(self, prompt_event: PromptEventMemoryObject) -> List[str]:
        """Generate comprehensive tags for prompt event memory indexing"""
        tags = [
            'prompt_event',
            prompt_event.event_type.value,
            f'quality_{prompt_event.memory_priority}',
        ]
        
        # Add semantic tags
        tags.extend(prompt_event.memory_tags.semantic_tags)
        
        # Add technical context tags
        tags.extend([f'tech_{tag}' for tag in prompt_event.memory_tags.technical_context])
        
        # Add collaboration context tags
        tags.extend([f'collab_{tag}' for tag in prompt_event.memory_tags.collaboration_context])
        
        # Add quality-based tags
        if prompt_event.is_high_quality:
            tags.append('high_quality')
        
        if prompt_event.user_feedback_score and prompt_event.user_feedback_score > 0.7:
            tags.append('positive_feedback')
        
        # Add adaptation tags
        if prompt_event.adaptations_applied:
            tags.extend([f'adaptation_{adapt}' for adapt in prompt_event.adaptations_applied])
        
        # Add performance tags
        if prompt_event.generation_time_ms:
            if prompt_event.generation_time_ms < 500:
                tags.append('fast_generation')
            elif prompt_event.generation_time_ms > 2000:
                tags.append('slow_generation')
        
        return list(set(tags))  # Remove duplicates
    
    async def enhance_context_with_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Enhance current context by retrieving relevant memories for a specific query.
        
        Returns additional memories that might be relevant to the current query.
        """
        try:
            relevant_memories = await self.memory_manager.retrieve_memories(
                user_id=self.user_id,
                query=query,
                importance_threshold=MemoryImportance.LOW,
                limit=5
            )
            
            # Filter out memories already in context
            context_memory_ids = {m['memory_id'] for m in self.context_memories}
            new_memories = [
                m for m in relevant_memories 
                if m['memory_id'] not in context_memory_ids
            ]
            
            logger.debug(f"Enhanced context with {len(new_memories)} additional memories")
            return new_memories
            
        except Exception as e:
            logger.error(f"Failed to enhance context with query: {e}")
            return []
    
    async def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of memory activity for this session"""
        return {
            'session_id': str(self.session_id),
            'user_id': self.user_id,
            'memories_created': len(self.session_memories),
            'context_memories_loaded': len(self.context_memories),
            'conversation_turns': len(self.conversation_buffer),
            'context_tokens_used': self.context_tokens_used
        }


class EnhancedSessionManager:
    """
    Enhanced session manager with integrated persistent memory support.
    
    Extends the original SessionManager to include automatic memory management,
    context reconstruction, and cross-session continuity.
    """
    
    def __init__(self, session_manager, memory_manager: MemoryManager):
        self.session_manager = session_manager
        self.memory_manager = memory_manager
        self.session_contexts: Dict[SessionID, SessionMemoryContext] = {}
        
        logger.info("Enhanced session manager initialized with memory support")
    
    async def create_session_with_memory(
        self, 
        request: SessionCreationRequest
    ) -> Tuple[Any, SessionMemoryContext]:
        """
        Create session with memory context initialization.
        
        Returns (SessionResponse, SessionMemoryContext) tuple.
        """
        # Create base session
        session_response = await self.session_manager.create_session(request)
        
        if session_response.state.value != "active":
            # Session creation failed, return without memory context
            return session_response, None
        
        # Initialize memory context
        memory_context = SessionMemoryContext(
            session_id=session_response.session_id,
            user_id=request.user_id or "anonymous",
            memory_manager=self.memory_manager
        )
        
        # Initialize context with relevant memories
        enhanced_prompt = await memory_context.initialize_context(
            request.custom_instructions
        )
        
        # Store memory context
        self.session_contexts[session_response.session_id] = memory_context
        
        # Store custom instructions as memory if provided
        if request.custom_instructions:
            await memory_context.store_extracted_fact(
                f"Custom instructions: {request.custom_instructions}",
                MemoryImportance.HIGH
            )
        
        logger.info(f"Created session {session_response.session_id} with memory context")
        
        return session_response, memory_context
    
    async def process_message_with_memory(
        self,
        session_id: SessionID,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None,
        prompt_event: Optional[PromptEventMemoryObject] = None
    ) -> Dict[str, Any]:
        """
        Process conversation turn with automatic memory storage and prompt event indexing.
        
        Returns memory processing results and context updates.
        """
        memory_context = self.session_contexts.get(session_id)
        if not memory_context:
            logger.warning(f"No memory context found for session {session_id}")
            return {'memory_stored': False, 'reason': 'no_context'}
        
        try:
            results = {}
            
            # Store conversation turn
            memory_id = await memory_context.store_conversation_turn(
                user_message=user_message,
                assistant_response=assistant_response,
                turn_metadata={'tools_used': tools_used or []}
            )
            results['conversation_memory_id'] = str(memory_id)
            
            # Store prompt event if provided (with immediate semantic indexing)
            if prompt_event:
                prompt_memory_id = await memory_context.store_prompt_event_memory(prompt_event)
                results['prompt_event_memory_id'] = str(prompt_memory_id)
                logger.info(f"Indexed prompt event {prompt_event.event_id} with immediate semantic embeddings")
            
            # Extract and store any user facts mentioned
            await self._extract_and_store_facts(memory_context, user_message)
            
            # Get enhanced context for future messages
            enhanced_memories = await memory_context.enhance_context_with_query(user_message)
            
            results.update({
                'memory_stored': True,
                'enhanced_context_count': len(enhanced_memories),
                'session_summary': await memory_context.get_session_summary()
            })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process message with memory: {e}")
            return {'memory_stored': False, 'reason': str(e)}
    
    async def index_prompt_event_immediately(
        self,
        session_id: SessionID,
        prompt_event: PromptEventMemoryObject
    ) -> Dict[str, Any]:
        """
        Immediately index a prompt event with semantic embeddings.
        
        This is called whenever a new prompt is generated to ensure
        immediate semantic indexing for future retrieval.
        """
        memory_context = self.session_contexts.get(session_id)
        if not memory_context:
            logger.warning(f"No memory context found for session {session_id} for prompt indexing")
            return {'indexed': False, 'reason': 'no_context'}
        
        try:
            # Store with immediate semantic indexing
            memory_id = await memory_context.store_prompt_event_memory(prompt_event)
            
            # Mark the indexing timestamp
            prompt_event.indexed_at = datetime.now(timezone.utc)
            
            logger.info(f"Immediately indexed prompt event {prompt_event.event_id} as memory {memory_id}")
            
            return {
                'indexed': True,
                'memory_id': str(memory_id),
                'prompt_event_id': str(prompt_event.event_id),
                'indexing_time': prompt_event.indexed_at.isoformat(),
                'quality_score': prompt_event.memory_tags.quality_score,
                'semantic_tags_count': len(prompt_event.memory_tags.semantic_tags)
            }
            
        except Exception as e:
            logger.error(f"Failed to immediately index prompt event: {e}")
            return {'indexed': False, 'reason': str(e)}
    
    async def _extract_and_store_facts(
        self, 
        memory_context: SessionMemoryContext, 
        user_message: str
    ):
        """
        Extract and store user facts from messages.
        
        This is a simple heuristic implementation - could be enhanced with NLP.
        """
        fact_patterns = [
            (r"my name is (\w+)", "User's name is {}"),
            (r"call me (\w+)", "User prefers to be called {}"),
            (r"i work at (\w+)", "User works at {}"),
            (r"i live in ([\w\s]+)", "User lives in {}"),
            (r"i prefer ([\w\s]+)", "User prefers {}"),
            (r"i don't like ([\w\s]+)", "User doesn't like {}"),
        ]
        
        import re
        user_message_lower = user_message.lower()
        
        for pattern, template in fact_patterns:
            match = re.search(pattern, user_message_lower)
            if match:
                fact = template.format(match.group(1))
                await memory_context.store_extracted_fact(fact, MemoryImportance.CRITICAL)
                logger.info(f"Extracted user fact: {fact}")
    
    async def destroy_session_with_memory(
        self, 
        session_id: SessionID, 
        reason: str = "user_request"
    ) -> bool:
        """
        Destroy session and cleanup memory context.
        
        Preserves stored memories but cleans up session-specific context.
        """
        # Get session summary before cleanup
        memory_context = self.session_contexts.get(session_id)
        session_summary = None
        if memory_context:
            session_summary = await memory_context.get_session_summary()
            logger.info(f"Session {session_id} memory summary: {session_summary}")
        
        # Clean up memory context
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
        
        # Destroy base session
        success = await self.session_manager.destroy_session(session_id, reason)
        
        return success
    
    async def get_user_memory_dashboard(self, user_id: UserID) -> Dict[str, Any]:
        """Get comprehensive memory dashboard for user"""
        try:
            # Get memory statistics
            memory_stats = await self.memory_manager.get_user_memory_stats(user_id)
            
            # Get recent memories
            recent_memories = await self.memory_manager.retrieve_memories(
                user_id=user_id,
                limit=10,
                include_content=False  # Just metadata for dashboard
            )
            
            # Get active session contexts
            active_contexts = [
                await ctx.get_session_summary()
                for session_id, ctx in self.session_contexts.items()
                if ctx.user_id == user_id
            ]
            
            return {
                'user_id': user_id,
                'memory_stats': memory_stats,
                'recent_memories': recent_memories,
                'active_sessions': active_contexts,
                'dashboard_generated_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate memory dashboard for {user_id}: {e}")
            return {'error': str(e)}
    
    def get_memory_context(self, session_id: SessionID) -> Optional[SessionMemoryContext]:
        """Get memory context for session"""
        return self.session_contexts.get(session_id)


# Factory function for easy integration
async def create_memory_enhanced_session_manager(
    base_session_manager,
    memory_config: Optional[MemoryConfiguration] = None
) -> EnhancedSessionManager:
    """
    Factory function to create memory-enhanced session manager.
    
    Handles initialization of memory components and integration.
    """
    if memory_config is None:
        memory_config = MemoryConfiguration()
    
    # Initialize memory manager
    memory_manager = MemoryManager(memory_config)
    await memory_manager.initialize()
    
    # Create enhanced session manager
    enhanced_manager = EnhancedSessionManager(base_session_manager, memory_manager)
    
    logger.info("Memory-enhanced session manager created successfully")
    return enhanced_manager