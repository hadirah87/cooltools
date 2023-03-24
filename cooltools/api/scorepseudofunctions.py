###Funcitons###


########################  snippets  #########################


#Define function for peak snippet
Function peak_snippet(contact_map, stall_list, stall_index, peak_index, size):

         begin function

         raise an error if peak_index is out of stall list range

         set snippet_matrix from contact_map containing peak with a selected size:
             snippet = contact_map[
                       (stall_list[stall_list_index] - size) : (stall_list[stall_list_index] + size),
                       (stall_list[stall_list_index + peak_index] - size) : (
                        stall_list[stall_list_index + peak_index] + size
                        ),
                        ]

         return snippet_matrix

         end function




#Define function for Tad snippet

Function tad_snippet(contact_map, stall_list, index):

         begin function

         raise an error if index is out of list range

         set tad_matrix between sequential stalls starting with index:
             tad = contact_map[
                   stall_list[index] : stall_list[index + 1] + 1,
                   stall_list[index] : stall_list[index + 1] + 1,
                   ] 

         return tad_matrix

         end function


#Define function for adjacent tads to extract in_tad area vs out_tad area.
Function tad_snippet(contact_map, stall_list, index, delta, diag_offset, max_distance):

         begin function

         getting tad_matrix from tad_snippet function

         set adjacent_tads starting with stall_index:
             pile_center = contact_map[
             stall_list[index] : stall_list[index + 2] + 1,
             stall_list[index] : stall_list[index + 2] + 1,
             ]
         
         raise an error if max_distance is larger than snippet

         set in_tad and out_tad areas:
             out_tad = np.zeros(np.shape(pile_center))
             out_tad[delta : tad_size - delta, tad_size + delta : -delta] = 1
             out_tad = np.tril(np.triu(out_tad, diag_offset), max_distance) > 0

             in_tad = np.zeros(np.shape(pile_center))
             in_tad[delta : tad_size - delta, delta : tad_size - delta] = 1
             in_tad[tad_size + delta : -delta, tad_size + delta : -delta] = 1
             in_tad = np.tril(np.triu(in_tad, diag_offset), max_distance) > 0

         return in_tad, out_tad, adjacent matrices

         end function



#Define function for flame snippets

       #vertical
       Function flame_snippet_vertical(contact_map, stall_list, index, width, edge_length):

         begin function

         set snippet_matrix from contact_map containing flame with a selected width:
             snippet = contact_map[
             (stall_list[n] + edge_length) : (stall_list[n + 1] - edge_length),
             (stall_list[n + 1] - width) : (stall_list[n + 1] + width),
             ]

         return snippet_matrix

         end function


       #horizontal
       Function flame_snippet_horizontal(contact_map, stall_list, index, width, edge_length):

         begin function

         set snippet_matrix from contact_map containing flame with a selected width:
             snippet = contact_map[
             (stall_list[n] - width) : (stall_list[n] + width),
             (stall_list[n] + edge_length) : (stall_list[n + 1] - edge_length),
             ]

         return snippet_matrix

         end function



############################### Scores ##################################


#Define function for peak score 

Function peak_lowerLeft(peak_snippet, peak_length, background_length):
   begin function 

   set the middle of the peak_snippet

   return lower_left score as peak snippet average over lower_left background:
          lowerleft_score=np.mean(
          peak_snippet[
          mid - peak_length : mid + peak_length, mid - peak_length : mid + peak_length] ) 
          / np.mean(
          peak_snippet[
            mid + peak_length : mid + background_length :,
            mid - background_length : mid - peak_length,
           ]
          )

   end function



Function peak_lowerRight(peak_snippet, peak_length, background_length):
   begin function 

   set the middle of the peak_snippet

   return lower_reft score as peak snippet average over lower_right background:
          lowerright_score=np.mean(
          peak_snippet[
            mid - peak_length : mid + peak_length, mid - peak_length : mid + peak_length
          ] ) / np.mean(
          peak_snippet[
            mid + peak_length : mid + background_length :,
            mid + peak_length : mid + background_length,
          ]
          )

   end function



Function peak_upperRight(peak_snippet, peak_length, background_length):
   begin function 

   set the middle of the peak_snippet

   return upperright score as peak snippet average over upper_right background:
           upperright_score=np.mean(
           peak_snippet[
            mid - peak_length : mid + peak_length, mid - peak_length : mid + peak_length
           ]
           ) / np.mean(
           avg_peaks[
            mid - background_length : mid - peak_length,
            mid + peak_length : mid + background_length,
           ]
           )

   end function


Function peak_upperLeft(peak_snippet, peak_length, background_length):
   begin function 

   set the middle of the peak_snippet

   return upper_left score as peak snippet average over upper_left background:
          upper_left_score= np.mean(
          peak_snippet[
          mid - peak_length : mid + peak_length, mid - peak_length : mid + peak_length
           ]
          ) / np.mean(
          peak_snippet[
          mid - background_length : mid - peak_length,
          mid - background_length : mid - peak_length,
          ]
          )

   end function


Function peak_score(peak_snippet, peak_length, background_length):
    begin function
    return average of peak scores for each corner:
           avg = (
           apa_upperRight(peak_snippet, peak_length, background_length)
           + apa_lowerRight(peak_snippet, peak_length, background_length)
           + apa_upperLeft(peak_snippet, peak_length, background_length)
           + apa_lowerLeft(peak_snippet, peak_length, background_length)
           ) / 4
    end function


# define the function for Tad score

Function tad_score(contact_map, stall_list, index, delta, diag_offset, max_distance)
    begin function

    set in_tad, out_tad, and adjacent matrices from tad_snippet_sectors function

    assert adjacent matrix to be in the shape of in_tad matrix 

    return score as average of in_tad matrix over out_tad score:
           tad_score=np.mean(pile_center[in_tad]) / np.mean(pile_center[out_tad])

    end function


#Flame scores 
#define the function for vertical flame score 

 Function flame_score_v(flame_snippet, flame_thickness, background_thickness):
    begin function

    set vertical middle of the snippet

    return the average of contacts on flame centered at middle with selected flame_thickness over background:
           flame_score_v = np.mean(
           avg_peaks[:, mid - flame_thickness // 2 : mid + flame_thickness // 2]
           ) / np.mean(
           avg_peaks[:, mid - background_thickness // 2 : mid + background_thickness // 2]
           )

          end function

    
#define the function for vertical flame score 

 Function flame_score_h(flame_snippet, flame_thickness, background_thickness):
    begin function

    set horizontal middle of the snippet

    return the average of contacts on flame centered at middle with selected flame_thickness over background 
           flame_score_h = np.mean(
           flame_snippet[mid - flame_thickness // 2 : mid + flame_thickness // 2, :]
           ) / np.mean(
           avg_peaks[mid - background_thickness // 2 : mid + background_thickness // 2, :]
           )

    end function

